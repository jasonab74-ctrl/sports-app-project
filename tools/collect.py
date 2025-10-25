#!/usr/bin/env python3
import os
import re
import json
import time
import math
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import requests
import feedparser
import yaml

# ============================
# CONFIG
# ============================

# how far back we're willing to consider (hours)
MAX_AGE_HOURS = 72  # 3 days rolling window

# how many headlines we keep
TOP_LIMIT = 20

# HTTP headers we use for RSS/Atom requests
FEED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "close",
}

# HTTP headers we use when we try to scrape og:image
SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "close",
}

# map funky source strings to nice canonical source names
SOURCE_CANON = {
    "hammer & rails": "Hammer & Rails",
    "hammer and rails": "Hammer & Rails",
    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "goldandblack": "GoldandBlack",
    "goldandblack.com": "GoldandBlack",
    "gold and black": "GoldandBlack",
    "rivals": "GoldandBlack",
    "on3 purdue": "On3 Purdue",
    "on3": "On3 Purdue",
    "yahoo sports purdue": "Yahoo Sports",
    "yahoo sports": "Yahoo Sports",
    "yahoo! sports": "Yahoo Sports",
    "cbs sports purdue": "CBS Sports",
    "cbs sports": "CBS Sports",
    "espn purdue": "ESPN",
    "espn": "ESPN",
    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",
    "purdue sports official": "PurdueSports",
    "field of 68": "Field of 68",
    "the field of 68": "Field of 68",
}

# fallback logos for when we absolutely cannot get an article image
# put these files in static/logos/ in your repo
FALLBACK_LOGOS = {
    "Hammer & Rails": "/static/logos/hammer_rails.png",
    "Journal & Courier": "/static/logos/journal_courier.png",
    "GoldandBlack": "/static/logos/goldandblack.png",
    "On3 Purdue": "/static/logos/on3.png",
    "Yahoo Sports": "/static/logos/yahoo.png",
    "CBS Sports": "/static/logos/cbs.png",
    "ESPN": "/static/logos/espn.png",
    "PurdueSports": "/static/logos/purdue.png",
    "Field of 68": "/static/logos/field68.png",
}

# ============================
# REGEX HELPERS
# ============================

IMG_TAG_RE = re.compile(
    r'<img[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# ============================
# HELPERS
# ============================

def canon_source(raw):
    """Return a nice source string."""
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())

def canonical_url(url):
    """
    Strip query + fragment for dedupe comparison.
    We still keep the original link for display, but we
    use this normalized key to avoid dupes.
    """
    if not url:
        return ""
    p = urlparse(url)
    p2 = p._replace(query="", fragment="")
    return urlunparse(p2)

def parse_date(entry):
    """
    Best guess at a datetime from a feedparser entry.
    We check published, updated, etc. If nothing usable,
    fallback to 'now' so it won't get filtered out just because
    a feed is missing timestamps.
    """
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def fetch_og_image(url):
    """
    Try to grab og:image (or first <img>) straight from the article page.
    We pretend to be Mobile Safari because a lot of sites gate images
    behind UA checks.
    """
    if not url:
        return None

    try:
        r = requests.get(
            url,
            headers=SCRAPE_HEADERS,
            timeout=4,
            allow_redirects=True,
        )
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

def extract_thumb_from_entry(entry, summary_html=None):
    """
    Step 1: RSS media_content/media_thumbnail
    Step 2: <img> in summary
    (We'll try fetch_og_image(url) later as a last pass)
    """
    # media_content / media_thumbnail, etc.
    media_blocks = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media_blocks, list) and media_blocks:
        cand = media_blocks[0].get("url")
        if cand:
            return cand

    # look inside summary/description for an <img>
    if summary_html:
        m = IMG_TAG_RE.search(summary_html)
        if m:
            return m.group(1)

    return None

def normalize_item(source_name, entry):
    """
    Turn a feed entry into our standard dict.
    """
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary_html = (
        entry.get("summary")
        or entry.get("summary_detail", {}).get("value")
        or entry.get("description")
        or ""
    )

    pub_dt = parse_date(entry)

    # first-pass thumb
    thumb = extract_thumb_from_entry(entry, summary_html)

    return {
        "title": title,
        "link": link,
        "source": canon_source(source_name),
        "date": pub_dt.isoformat(),  # UTC iso string
        "image": thumb or None,
    }

def looks_like_football(text):
    """
    Hard football filter.
    If this returns True -> toss the item completely.
    """
    football_terms = [
        "football",
        "qb", "quarterback",
        "touchdown", "wide receiver",
        "linebacker", "safety", "defensive coordinator",
        "ryan walters", "coach walters", "walters'",
        "big ten tiers",  # careful: sometimes CBB writes that phrase too,
                          # but usually football power rankings use it
    ]
    t = text.lower()
    return any(term in t for term in football_terms)

def is_relevant_purdue(item):
    """
    SUPER SIMPLE NOW:
    – Must mention Purdue / Boilermakers somewhere in title or summary blob.
    – If it screams 'football', throw it out completely.
    – Anything else -> keep (we do NOT require 'basketball' keyword).
    """
    blob = f"{item.get('title','')} {item.get('source','')}"
    # must mention Purdue somehow
    if not any(w in blob.lower() for w in ("purdue", "boilermaker", "boilermakers")):
        return False
    # reject obvious football
    if looks_like_football(blob):
        return False
    return True

def dedupe(items):
    """
    Deduplicate by (normalized URL OR similar title).
    Keep the first/top (which for us will generally be newer).
    """
    out = []
    seen_urls = set()
    for it in items:
        url_key = canonical_url(it.get("link", ""))

        # check if we already saw basically this URL or effectively this exact/super-similar title
        dup = False

        if url_key and url_key in seen_urls:
            dup = True

        else:
            # soft title match: strip punctuation / lowercase
            tnorm = re.sub(r"[^a-z0-9]+", " ", it.get("title","").lower()).strip()
            for kept in out:
                knorm = re.sub(r"[^a-z0-9]+", " ", kept.get("title","").lower()).strip()
                if knorm == tnorm:
                    dup = True
                    break

        if not dup:
            out.append(it)
            if url_key:
                seen_urls.add(url_key)

    return out

def add_thumbnails(items):
    """
    For any item missing 'image', attempt og:image scrape.
    NOTE: This is potentially slow / can fail for paywalled sources,
    so we keep timeout very short and just move on.
    """
    for it in items:
        if it.get("image"):
            continue
        img = fetch_og_image(it.get("link"))
        if img:
            it["image"] = img
    return items

def apply_fallback_logos(items):
    """
    For anything STILL missing image, give it a branded fallback
    based on the source. This keeps cards from looking blank.
    """
    for it in items:
        if not it.get("image"):
            logo = FALLBACK_LOGOS.get(it.get("source"))
            if logo:
                it["image"] = logo
    return items

def atomic_write_json(path, data_obj):
    """
    Write JSON atomically (tmp file + rename) so GitHub Pages never
    serves a half-written file.
    """
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

# ============================
# CORE
# ============================

def collect_team(team_slug, feed_list, out_path):
    """
    Pull all feeds for a team, normalize, filter, dedupe, sort,
    slice to TOP_LIMIT, enrich thumbnails, apply logos,
    and then write items.json.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    raw_items = []

    for feed_def in feed_list:
        source_name = feed_def.get("name", "Source")
        url = feed_def.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        # Take only first ~60 entries from each feed for sanity
        for entry in parsed.entries[:60]:
            item = normalize_item(source_name, entry)

            # age gate
            try:
                dt = datetime.fromisoformat(item["date"])
            except Exception:
                dt = datetime.now(timezone.utc)

            if dt < cutoff:
                continue

            # Purdue filter (and "no football")
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
            return datetime.now(timezone.utc)
    deduped.sort(key=_dt, reverse=True)

    # take top N
    top_items = deduped[:TOP_LIMIT]

    # thumbnail enrichment + fallback logos
    top_items = add_thumbnails(top_items)
    top_items = apply_fallback_logos(top_items)

    data_obj = {"items": top_items, "updated": datetime.now(timezone.utc).isoformat()}

    atomic_write_json(out_path, data_obj)
    print(f"[{team_slug}] wrote {out_path} ({len(top_items)} items)")

def main():
    """
    Entry point.
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
        raise SystemExit("No teams configured in feeds.yaml or TEAMS env var")

    for team in teams:
        if team not in feeds_by_team:
            print(f"[WARN] {team} not in feeds.yaml, skipping")
            continue

        out_path = f"static/teams/{team}/items.json"
        collect_team(team, feeds_by_team[team], out_path)

if __name__ == "__main__":
    main()