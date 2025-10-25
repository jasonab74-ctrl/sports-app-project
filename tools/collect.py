#!/usr/bin/env python3
import os
import re
import json
import math
import time
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import requests
import feedparser
import yaml

# -------------------------------------------------------------------
# CONFIG / CONSTANTS
# -------------------------------------------------------------------

# how "new" an article must be to qualify (rolling window)
MAX_AGE_DAYS = 3  # last ~72h

# how many stories we actually surface
TOP_N = 20

# headers for RSS / page fetches (helps with user-agent blocks)
FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PurdueMBBFeedBot/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Simple source-name canonicalization so duplicates merge cleanly
SOURCE_CANON = {
    "hammer and rails": "Hammer & Rails",
    "hammer & rails": "Hammer & Rails",
    "hammerandrails": "Hammer & Rails",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "journal courier": "Journal & Courier",

    "goldandblack": "GoldandBlack",
    "goldandblack.com": "GoldandBlack",
    "gold and black": "GoldandBlack",
    "goldandblack (rivals)": "GoldandBlack",

    "on3 purdue": "On3 Purdue",
    "on3": "On3 Purdue",

    "espn": "ESPN",
    "espn purdue": "ESPN",

    "cbs sports": "CBS Sports",
    "cbs": "CBS Sports",

    "yahoo sports": "Yahoo Sports",
    "yahoo! sports": "Yahoo Sports",
    "yahoo": "Yahoo Sports",

    "field of 68": "Field of 68",
    "fieldof68": "Field of 68",

    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",
    "purduesports": "PurdueSports",
}

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def canon_source(raw):
    """Map raw source/feed title to a nice display name."""
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())

def canonical_url(url):
    """
    Normalize URL for dedupe:
    - strip query/fragment
    - lowercase hostname
    """
    if not url:
        return ""
    p = urlparse(url)
    clean = p._replace(
        query="",
        fragment="",
        netloc=p.netloc.lower(),
    )
    return urlunparse(clean)

def parse_date(entry):
    """
    Pull a datetime (UTC) from feedparser entry.
    We'll try published_parsed, updated_parsed, etc.
    If all else fails, now().
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
    Try to grab a social/preview image for an article by loading
    the article HTML (quick + best effort).
    1. og:image
    2. first <img>
    Returns None if nothing obvious.
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

        # 2) fallback: first <img>
        m2 = IMG_TAG_RE.search(html)
        if m2:
            return m2.group(1).strip()

    except Exception:
        return None

    return None

def extract_thumb_from_entry(entry, summary_html):
    """
    thumbnail priority:
    1. RSS media_content/media_thumbnail
    2. <img> in summary/description
    We do *not* hit the network here (that happens later as a fallback).
    """
    # Step 1: "media_content" or "media_thumbnail"
    media_blocks = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media_blocks, list) and media_blocks:
        cand = media_blocks[0].get("url")
        if cand:
            return cand

    # Step 2: <img> in summary/description
    if summary_html:
        m = IMG_TAG_RE.search(summary_html)
        if m:
            return m.group(1)

    return None

def normalize_item(source_name, entry):
    """
    Convert a raw feedparser entry into our normalized dict:
    {
        "title": ...,
        "link": ...,
        "source": ...,
        "date": <iso8601 UTC>,
        "image": <thumb or None>
    }
    """
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()

    # summary vs description can vary between feeds
    summary_html = entry.get("summary") or entry.get("description") or ""

    pub_dt = parse_date(entry)
    thumb = extract_thumb_from_entry(entry, summary_html)

    return {
        "title": title,
        "link": link,
        "source": canon_source(source_name),
        "date": pub_dt.isoformat(),  # keep in UTC, isoformat
        "image": thumb or None,
    }

def looks_like_football(text):
    """
    "Do we think this is clearly about *football* / football coach / Big Ten tiers football?"
    If yes -> we exclude.
    (We really only want men's basketball content.)
    """
    if not text:
        return False
    t = text.lower()

    football_terms = [
        "football",
        "qb", "quarterback",
        "touchdown", "wide receiver",
        "linebacker", "safety", "defensive coordinator",
        "ryan walters", "coach walters", "walters'",
    ]

    # Heuristic for "Big Ten tiers": sometimes it's basketball, sometimes football.
    # We'll handle this *lightly* here: Big Ten tiers WITH 'qb' or 'defense' will be caught above.
    # Otherwise we'll allow it through. We'll refine in is_relevant_purdue.

    return any(term in t for term in football_terms)

def is_relevant_purdue(item):
    """
    Keep it if:
    - It mentions Purdue / Boilermakers somewhere in title+summary blob.
    - It is NOT obviously football.
    We don't require the word 'basketball'. We lean permissive.
    """
    blob = f"{item.get('title','')} {item.get('source','')}".lower()

    # must mention Purdue or Boilermakers
    if not any(w in blob for w in ["purdue", "boilermaker", "boilermakers"]):
        return False

    # reject obvious football
    if looks_like_football(blob):
        return False

    return True

def dedupe(items):
    """
    Deduplicate by very-similar title OR same canonical URL.
    We'll keep the first occurrence (which should be newest once we sort later).
    """
    out = []
    seen_urls = set()

    def similar(a, b):
        # quick+dirty title similarity:
        # compare lowercase words overlap. If it's like 80% same, call it duplicate.
        aw = set(a.lower().split())
        bw = set(b.lower().split())
        if not aw or not bw:
            return False
        inter = len(aw & bw)
        bigger = max(len(aw), len(bw))
        ratio = inter / bigger if bigger else 0.0
        return ratio >= 0.8

    for it in items:
        url_key = canonical_url(it.get("link", ""))

        # URL dup check
        if url_key and url_key in seen_urls:
            continue

        # fuzzy title dup check
        title = it.get("title", "")
        dup = False
        for kept in out:
            if similar(title, kept.get("title", "")):
                dup = True
                break

        if not dup:
            out.append(it)
            if url_key:
                seen_urls.add(url_key)

    return out

def add_thumbnails(items):
    """
    For any story missing image, try to fetch the article and
    grab og:image or first <img>.
    We only do this for the list we actually show (TOP_N-ish),
    so it's cheap.
    """
    for it in items:
        if it.get("image"):
            continue
        img = fetch_og_image(it.get("link"))
        if img:
            it["image"] = img
    return items

def atomic_write_json(path, data_obj):
    """
    Write JSON to disk safely (temp file then rename).
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

# -------------------------------------------------------------------
# CORE
# -------------------------------------------------------------------

def collect_team(team_slug, feeds_for_team, out_path):
    """
    team_slug: e.g. "purdue-mbb"
    feeds_for_team: list of {name: "...", url: "..."} dicts
    out_path: e.g. "static/teams/purdue-mbb/items.json"
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)

    raw_items = []

    # pull from every feed
    for feed_def in feeds_for_team:
        source_name = feed_def.get("name", "Source")
        url = feed_def.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        # take first ~60 entries from each feed (usually plenty)
        for entry in parsed.entries[:60]:
            item = normalize_item(source_name, entry)

            # age gate
            try:
                dt = datetime.fromisoformat(item["date"])
            except Exception:
                dt = now

            if dt < cutoff:
                continue

            raw_items.append(item)

    # basic Purdue/basketball relevance filter
    filtered = [it for it in raw_items if is_relevant_purdue(it)]

    # sort newest first
    filtered.sort(
        key=lambda i: datetime.fromisoformat(i["date"]),
        reverse=True,
    )

    # dedupe similar links/titles
    deduped = dedupe(filtered)

    # take top N
    top_items = deduped[:TOP_N]

    # fill in missing thumbnails (best effort)
    top_items = add_thumbnails(top_items)

    # final payload
    payload = {
        "team": team_slug,
        "updated": now.isoformat(),
        "items": top_items,
    }

    # write to disk
    atomic_write_json(out_path, payload)
    print(f"[OK] wrote {len(top_items)} items to {out_path}")

def main():
    """
    - Look at TEAMS env var, e.g. "purdue-mbb"
      (you can support multiple like "purdue-mbb,another-team" later)
    - Load feeds from src/feeds.yaml
    - For each team: collect + write static/teams/<team>/items.json
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