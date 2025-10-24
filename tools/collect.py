import os
import re
import json
import yaml
import feedparser
import requests
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

# =====================================================
# CONFIG
# =====================================================

MAX_RESULTS = 20            # we only ship top 20
MAX_AGE_DAYS = 14           # rolling window
DEDUP_TITLE_SIM = 85        # fuzzy title dedupe threshold
HTTP_TIMEOUT = 6            # seconds for thumbnail scrape

FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (PurdueMBBHub/1.0)"
}

# Canonical source names we want to show in UI
SOURCE_CANON = {
    "hammer & rails": "Hammer & Rails",
    "hammerandrials": "Hammer & Rails",
    "hammerandrails": "Hammer & Rails",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "jconline": "Journal & Courier",

    "goldandblack": "GoldandBlack (Rivals)",
    "gold and black": "GoldandBlack (Rivals)",
    "rivals": "GoldandBlack (Rivals)",
    "goldandblack.com": "GoldandBlack (Rivals)",

    "on3 purdue": "On3 Purdue",
    "on3.com": "On3 Purdue",
    "on3": "On3 Purdue",

    "espn": "ESPN",
    "espn.com": "ESPN",

    "yahoo sports": "Yahoo Sports",
    "sports.yahoo.com": "Yahoo Sports",
    "yahoo!": "Yahoo Sports",

    "cbs sports": "CBS Sports",
    "cbssports.com": "CBS Sports",

    "field of 68": "Field of 68",
    "the field of 68": "Field of 68",

    "the athletic": "The Athletic",
    "theathletic.com": "The Athletic",

    "stadium / jeff goodman": "Stadium / Jeff Goodman",
    "stadium": "Stadium / Jeff Goodman",
    "watchstadium.com": "Stadium / Jeff Goodman",

    "associated press (ap)": "Associated Press (AP)",
    "ap news": "Associated Press (AP)",
    "apnews.com": "Associated Press (AP)",
    "associated press": "Associated Press (AP)",

    "big ten network": "Big Ten Network",
    "btn.com": "Big Ten Network",
    "btn": "Big Ten Network",

    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",
}

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# =====================================================
# HELPERS
# =====================================================

def canon_source(raw):
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())

def canonical_url(url):
    """Strip query + fragment for dedupe comparisons."""
    if not url:
        return ""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def parse_date(entry):
    """
    Grab published/updated/created, fall back to now.
    """
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def fetch_og_image(url):
    """
    Best-effort fetch of article HTML and pull og:image.
    We keep this short + silent. If it fails, just None.
    """
    if not url:
        return None
    try:
        r = requests.get(url, headers=FEED_HEADERS, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
        html = r.text
        # 1) og:image
        m = OG_IMAGE_RE.search(html)
        if m:
            return m.group(1).strip()
        # 2) first <img> fallback
        m2 = IMG_TAG_RE.search(html)
        if m2:
            return m2.group(1).strip()
    except Exception:
        return None
    return None

def extract_thumb_from_entry(entry, summary_html):
    """
    Step 1: RSS media_content/media_thumbnail
    Step 2: <img> in summary
    Step 3: later we'll try fetch_og_image(url)
    """
    # media_content / media_thumbnail
    media_blocks = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media_blocks, list) and media_blocks:
        cand = media_blocks[0].get("url")
        if cand:
            return cand

    # <img> in summary/description
    if summary_html:
        m = IMG_TAG_RE.search(summary_html)
        if m:
            return m.group(1)

    return None

def normalize_item(source_name, entry):
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary_html = (entry.get("summary") or entry.get("description") or "").strip()
    pub_dt = parse_date(entry)

    # first-pass thumb
    thumb = extract_thumb_from_entry(entry, summary_html)

    return {
        "source": canon_source(source_name),
        "title": title,
        "link": link,
        "date": pub_dt.isoformat(),   # UTC iso
        "summary": summary_html[:500],
        "image": thumb or None,
    }

def looks_like_football(text):
    """
    Hard filter for football.
    If this says True, we toss it completely.
    """
    football_terms = [
        "football",
        "qb", "quarterback",
        "touchdown", "wide receiver",
        "linebacker", "safety", "defensive coordinator",
        "ryan walters", "coach walters", "walters' defense",
        "big ten tiers"  # careful: sometimes CBB too, but this is mostly CFB in October. We'll leave it.
    ]
    t = text.lower()
    return any(term in t for term in football_terms)

def is_relevant_purdue(item):
    """
    SUPER SIMPLE NOW:
    - Must mention Purdue / Boilermakers somewhere (title or summary)
    - If it screams 'football', throw it out
    Anything else -> keep. We do NOT require 'basketball' keywords.
    """
    blob = f"{item.get('title','')} {item.get('summary','')}".lower()

    # must mention Purdue
    if not any(w in blob for w in ["purdue", "boilermaker", "boilermakers"]):
        return False

    # reject obvious football
    if looks_like_football(blob):
        return False

    return True

def dedupe(items):
    """
    Deduplicate on canonical URL or fuzzy-similar title.
    """
    out = []
    seen_urls = set()

    for it in items:
        url_key = canonical_url(it.get("link"))
        title_key = (it.get("title") or "").strip().lower()

        # same URL? skip
        if url_key and url_key in seen_urls:
            continue

        # similar title? skip
        dup = False
        for kept in out:
            kept_title = (kept.get("title") or "").strip().lower()
            if fuzz.token_set_ratio(title_key, kept_title) >= DEDUP_TITLE_SIM:
                dup = True
                break

        if not dup:
            out.append(it)
            if url_key:
                seen_urls.add(url_key)

    return out

def add_thumbnails(items):
    """
    For any item missing image, attempt og:image scrape.
    Tries to enrich the first ~20 only (which is already all we keep).
    """
    for it in items:
        if it.get("image"):
            continue
        img = fetch_og_image(it.get("link"))
        if img:
            it["image"] = img
    return items

def atomic_write_json(path, data_obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=os.path.dirname(path),
        encoding="utf-8"
    ) as tmp:
        json.dump(data_obj, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

# =====================================================
# CORE
# =====================================================

def collect_team(team_slug, feeds_conf, out_path):
    """
    Pull feeds for a team, filter, dedupe, sort newest->oldest,
    cap at 20, write items.json ALWAYS.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    raw_items = []

    for feed_def in feeds_conf:
        source_name = feed_def.get("name", "Source")
        url = feed_def.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        for entry in parsed.entries[:60]:
            item = normalize_item(source_name, entry)

            # age gate
            try:
                dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)

            if dt < cutoff:
                continue

            # Purdue check (basketball-ish via "not football")
            if not is_relevant_purdue(item):
                continue

            raw_items.append(item)

    # dedupe
    deduped = dedupe(raw_items)

    # sort newest first
    def _dt(i):
        try:
            return datetime.fromisoformat(i["date"].replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
    deduped.sort(key=_dt, reverse=True)

    # top 20
    top_items = deduped[:MAX_RESULTS]

    # fetch thumbnails for anything missing
    top_items = add_thumbnails(top_items)

    # ALWAYS write out_path, even if empty
    atomic_write_json(out_path, {"items": top_items})
    print(f"[{team_slug}] wrote {len(top_items)} items -> {out_path}")

def main():
    """
    TEAMS env var: "purdue-mbb"
    Loads src/feeds.yaml
    """
    with open("src/feeds.yaml", "r", encoding="utf-8") as f:
        feeds_by_team = yaml.safe_load(f)

    teams_env = os.environ.get("TEAMS", "").strip()
    if teams_env:
        teams = [t.strip() for t in teams_env.split(",") if t.strip()]
    else:
        teams = list(feeds_by_team.keys())

    if not teams:
        raise SystemExit("No teams configured in feeds.yaml / TEAMS.")

    for team in teams:
        if team not in feeds_by_team:
            print(f"[WARN] {team} not in feeds.yaml, skipping.")
            continue

        out_path = f"static/teams/{team}/items.json"
        collect_team(team, feeds_by_team[team], out_path)

if __name__ == "__main__":
    main()