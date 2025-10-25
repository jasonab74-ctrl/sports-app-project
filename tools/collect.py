#!/usr/bin/env python3
import os, re, json, tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse
import requests
import feedparser
import yaml
from difflib import SequenceMatcher

# -------------------------------------------------
# CONSTANTS / CONFIG
# -------------------------------------------------

# how far back we allow (hours)
MAX_AGE_HOURS = 48  # keep last ~2 days of stuff

# how many headlines total we keep per team
MAX_ITEMS = 20

# headers so sites don't block us
FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PurdueMBBBot/1.0)"
}

# map weird source strings to nice display names
SOURCE_CANON = {
    "hammer and rails": "Hammer & Rails",
    "hammer & rails": "Hammer & Rails",
    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "on3 purdue": "On3 Purdue",
    "on3": "On3 Purdue",
    "goldandblack": "GoldandBlack",
    "gold and black": "GoldandBlack",
    "cbs sports": "CBS Sports",
    "cbs sports purdue": "CBS Sports",
    "espn": "ESPN",
    "yahoo sports": "Yahoo Sports",
    "yahoo! sports": "Yahoo Sports",
    "field of 68": "Field of 68",
    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",
}

# regex helpers for thumbnail extraction
IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def canon_source(raw):
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())

def canonical_url(url):
    """
    Strip query + fragment for dedupe comparison
    """
    if not url:
        return ""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def parse_date(entry):
    """
    Try several date fields from feedparser entry.
    Returns aware datetime (UTC).
    """
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    # fallback = now
    return datetime.now(timezone.utc)

def fetch_og_image(url):
    """
    Best-effort fetch of article HTML and pull og:image or first <img>.
    Silent fail if blocked/slow.
    """
    if not url:
        return None
    try:
        r = requests.get(url, headers=FEED_HEADERS, timeout=5)
        if r.status_code != 200:
            return None
        html = r.text

        # 1) og:image
        m = OG_IMAGE_RE.search(html)
        if m:
            return m.group(1).strip()

        # 2) first <img>
        m2 = IMG_TAG_RE.search(html)
        if m2:
            return m2.group(1).strip()

    except Exception:
        return None

    return None

def extract_thumb_from_entry(entry, summary_html):
    """
    Step 1: RSS media_content / media_thumbnail
    Step 2: <img> in summary
    Step 3: (later) we'll try fetch_og_image(url) in add_thumbnails()
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
    summary_html = entry.get("summary") or entry.get("description") or ""
    pub_dt = parse_date(entry)

    # first-pass thumb
    thumb = extract_thumb_from_entry(entry, summary_html)

    return {
        "source": canon_source(source_name),
        "title": title,
        "link": link,
        "date": pub_dt.isoformat(),  # UTC iso string
        "image": thumb or None,
    }

def looks_like_football(text):
    """
    Hard filter for football.
    If this returns True, we drop it.
    """
    football_terms = [
        "football",
        "qb", "quarterback",
        "touchdown", "wide receiver",
        "linebacker", "safety", "defensive coordinator",
        "ryan walters", "coach walters", "walters'",
        "big ten tiers",  # NOTE: football-y most of the time
    ]
    t = text.lower()
    return any(term in t for term in football_terms)

def is_relevant_purdue(item):
    """
    SUPER SIMPLE NOW:
    – Must mention Purdue / Boilermakers somewhere
    – If it screams 'football', throw it out
    – Anything else -> keep. We do NOT require 'basketball'
    """
    blob = f"{item.get('title','')} {item.get('source','')}"
    # must mention Purdue
    if not any(w in blob.lower() for w in ["purdue", "boilermaker", "boilermakers"]):
        return False

    # reject obvious football
    if looks_like_football(blob):
        return False

    return True

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def dedupe(items):
    """
    Remove near-duplicates:
    - same canonical URL
    - or highly-similar title (~0.9+)
    Keep first occurrence.
    """
    out = []
    seen_urls = set()
    for it in items:
        url_key = canonical_url(it.get("link", "")) or None
        title_i = it.get("title", "")
        dup = False

        # same cleaned link?
        if url_key and url_key in seen_urls:
            dup = True

        # fuzzy title?
        if not dup:
            for kept in out:
                if similar(kept.get("title",""), title_i) > 0.9:
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
        json.dump(data_obj, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

# -------------------------------------------------
# CORE
# -------------------------------------------------

def collect_team(team_slug, feeds_for_team, out_path):
    """
    team_slug example: "purdue-mbb"
    feeds_for_team: list of {name: "...", url: "..."}
    out_path: where to write items.json
    """
    print(f"[collect] Team {team_slug}: {len(feeds_for_team)} feeds")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    raw_items = []

    # pull from each feed
    for feed_def in feeds_for_team:
        source_name = feed_def.get("name", "Source")
        url = feed_def.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        # just look at first ~60 entries, newest first
        for entry in parsed.entries[:60]:
            item = normalize_item(source_name, entry)

            # age gate
            try:
                dt = datetime.fromisoformat(item["date"])
            except Exception:
                dt = datetime.now(timezone.utc)

            if dt < cutoff:
                continue

            # Purdue & not football
            if not is_relevant_purdue(item):
                continue

            raw_items.append(item)

    # dedupe
    deduped = dedupe(raw_items)

    # sort newest first
    def _dt(i):
        try:
            return datetime.fromisoformat(i["date"])
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    deduped.sort(key=_dt, reverse=True)

    # trim top MAX_ITEMS
    top_items = deduped[:MAX_ITEMS]

    # try thumbnails for missing ones
    top_items = add_thumbnails(top_items)

    # final payload
    payload = {
        "team": team_slug,
        "updated": datetime.now(timezone.utc).isoformat(),
        "items": top_items,
    }

    atomic_write_json(out_path, payload)
    print(f"[collect] wrote {out_path} with {len(top_items)} items")

def main():
    """
    TEAMS env var: "purdue-mbb,purdue-wbb"
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
        raise SystemExit("No teams configured in feeds.yaml / TEAMS env")

    for team in teams:
        if team not in feeds_by_team:
            print(f"[WARN] {team} not in feeds.yaml, skipping")
            continue
        out_path = f"static/teams/{team}/items.json"
        collect_team(team, feeds_by_team[team], out_path)

if __name__ == "__main__":
    main()