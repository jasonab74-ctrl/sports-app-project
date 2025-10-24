import os
import re
import json
import yaml
import feedparser
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

# ----------------------------
# Tunables / knobs
# ----------------------------
MAX_RESULTS = 20
MAX_AGE_DAYS = 14  # allow ~2 weeks of content so slow periods don't look empty
DEDUP_TITLE_SIM_THRESHOLD = 85
RECENCY_HALFLIFE_HOURS = 18.0

FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (PurdueMBBHub/1.0; +https://example.local)"
}

# Weighting: newer + insider > stale + national fluff
TRUST_WEIGHTS = {
    "official":   1.00,
    "insiders":   0.95,
    "beat":       0.90,
    "local":      0.80,
    "national":   0.75,
    "blog":       0.60,
    "fan_forum":  0.50,
}

# Canonical source names so the UI doesn't show tiny variations
SOURCE_CANON = {
    "hammer & rails": "Hammer & Rails",
    "hammerandrials": "Hammer & Rails",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "jconline": "Journal & Courier",

    "goldandblack": "GoldandBlack (Rivals)",
    "gold and black": "GoldandBlack (Rivals)",
    "rivals": "GoldandBlack (Rivals)",
    "goldandblack.com": "GoldandBlack (Rivals)",

    "on3 purdue": "On3 Purdue",
    "on3.com": "On3 Purdue",

    "espn": "ESPN",
    "espn.com": "ESPN",

    "yahoo sports": "Yahoo Sports",
    "sports.yahoo.com": "Yahoo Sports",

    "cbs sports": "CBS Sports",
    "cbssports.com": "CBS Sports",

    "field of 68": "Field of 68",
    "the athletic": "The Athletic",
    "theathletic.com": "The Athletic",

    "stadium / jeff goodman": "Stadium / Jeff Goodman",
    "watchstadium.com": "Stadium / Jeff Goodman",

    "associated press (ap)": "Associated Press (AP)",
    "associated press (cbb)": "Associated Press (AP)",
    "ap news": "Associated Press (AP)",
    "apnews.com": "Associated Press (AP)",

    "big ten network": "Big Ten Network",
    "btn.com": "Big Ten Network",
}

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

def canon_source(raw):
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())

def _canonicalize_url(url):
    if not url:
        return ""
    p = urlparse(url)
    # strip query/fragment for dedup
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def _parse_date(entry):
    """
    Try published_parsed, updated_parsed, etc. Fall back to now.
    """
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def _extract_best_image(entry, summary_html):
    """
    Best-effort image picker:
    1. RSS media_content / media_thumbnail
    2. First <img src="..."> in summary HTML
    """
    # media_content / media_thumbnail
    media_blocks = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media_blocks, list) and media_blocks:
        candidate = media_blocks[0].get("url")
        if candidate:
            return candidate

    # scan summary HTML for <img src="...">
    if summary_html:
        m = IMG_TAG_RE.search(summary_html)
        if m:
            return m.group(1)

    return None

def _normalize_item(source_name, trust_level, entry):
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary_html = (entry.get("summary") or entry.get("description") or "").strip()

    pub_dt = _parse_date(entry)

    thumb = _extract_best_image(entry, summary_html)

    return {
        "source": canon_source(source_name),
        "trust": trust_level,
        "title": title,
        "link": link,
        "date": pub_dt.isoformat(),
        "summary": summary_html[:500],
        "image": thumb
    }

def _is_mbb_related(item):
    """
    Relaxed Purdue Men's Basketball relevance test.

    Goal:
    - Keep Purdue hoops, roster, recruiting, preseason camp, B1G hoops talk.
    - Drop obvious Purdue football-only content.

    We used to require super basketball-specific words.
    Now we:
    - require "purdue" OR "boilermaker(s)" somewhere
    - AND NOT obvious football-only terms.
    - bonus keep terms that smell like hoops.
    """
    text = f"{item.get('title','')} {item.get('summary','')}".lower()

    # Must mention Purdue in some form, otherwise it's generic national filler.
    if not any(w in text for w in ["purdue", "boilermaker", "boilermakers"]):
        return False

    # Hard reject football-y coverage that hijacks feed.
    reject_terms = [
        "football", "qb", "quarterback", "touchdown",
        "wide receiver", "linebacker", "defensive coordinator",
        "big ten schedule quirks to know",  # mostly football schedule chatter
        "walters",  # Ryan Walters football head coach
    ]
    if any(r in text for r in reject_terms):
        return False

    # If clearly hoopsy terms appear, great, auto-keep.
    keep_terms = [
        "basketball", "guard", "forward", "center",
        "roster", "rotation", "backcourt", "frontcourt",
        "recruit", "recruiting", "commit", "commitment",
        "ncaa tournament", "camp standouts", "practice",
        "offseason check-in", "chemistry", "painter", "matt painter"
    ]
    if any(k in text for k in keep_terms):
        return True

    # Fallback: still Purdue mention, not flagged football.
    # We'll allow it. This is how we surface new-but-not-explicitly-hoops
    # preseason stuff like "Purdue outlook", which is often basketball.
    return True

def _dedup(items):
    """
    Deduplicate by canonical URL and fuzzy-similar title.
    """
    out = []
    seen_urls = set()

    for it in items:
        url = _canonicalize_url(it.get("link"))
        title = (it.get("title") or "").strip().lower()

        # same URL => drop
        if url and url in seen_urls:
            continue

        # fuzzy same title => drop
        is_dup = False
        for oi in out:
            existing_title = (oi.get("title") or "").strip().lower()
            if fuzz.token_set_ratio(title, existing_title) >= DEDUP_TITLE_SIM_THRESHOLD:
                is_dup = True
                break

        if not is_dup:
            out.append(it)
            if url:
                seen_urls.add(url)

    return out

def _recency_weight(dt):
    """
    Exponential decay. Newer stories get higher score.
    """
    now = datetime.now(timezone.utc)
    hours_old = max(0, (now - dt).total_seconds() / 3600.0)
    return 0.5 ** (hours_old / RECENCY_HALFLIFE_HOURS)

def _score(item):
    """
    Final ranking score = recency + trust.
    """
    trust_raw = (item.get("trust") or "").lower()
    trust_val = TRUST_WEIGHTS.get(trust_raw, 0.6)

    try:
        dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)

    rec_val = _recency_weight(dt)

    return (0.7 * rec_val) + (0.3 * trust_val)

def _atomic_write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=os.path.dirname(path),
        encoding="utf-8"
    ) as tmp:
        json.dump(obj, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

def collect_team(team_slug, feeds, out_path):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    pulled_items = []

    for feed_conf in feeds:
        source_name = feed_conf.get("name", "Source")
        trust_level = feed_conf.get("trust_level", "national")
        url = feed_conf.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        for entry in parsed.entries[:50]:
            item = _normalize_item(source_name, trust_level, entry)

            # filter by age
            try:
                dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)

            if dt < cutoff:
                continue

            # filter by "Purdue men's basketball-ish"
            if not _is_mbb_related(item):
                continue

            pulled_items.append(item)

    # dedupe similar headlines
    deduped = _dedup(pulled_items)

    # newest + trusted first
    deduped.sort(key=_score, reverse=True)

    top_items = deduped[:MAX_RESULTS]

    if not top_items:
        print(f"[{team_slug}] No qualifying Purdue MBB stories. Keeping old file.")
        return

    _atomic_write(out_path, {"items": top_items})
    print(f"[{team_slug}] wrote {len(top_items)} items -> {out_path}")

def main():
    conf = yaml.safe_load(open("src/feeds.yaml", "r", encoding="utf-8"))

    teams_env = os.environ.get("TEAMS", "").strip()
    teams = [t.strip() for t in teams_env.split(",") if t.strip()] if teams_env else list(conf.keys())
    if not teams:
        raise SystemExit("No teams configured in feeds.yaml.")

    for team in teams:
        if team not in conf:
            print(f"Team {team} not found in feeds.yaml; skipping.")
            continue

        out_path = f"static/teams/{team}/items.json"
        collect_team(team, conf[team], out_path)

if __name__ == "__main__":
    main()