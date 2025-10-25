#!/usr/bin/env python3
"""
collect.py
Build the rolling "top headlines" feed for each team.

What this script does:
- Load RSS/Atom feeds for one or more teams from src/feeds.yaml
- Normalize each entry into {source,title,link,date,image}
- Filter for relevance (Purdue hoops, ditch obvious football)
- Sort newest-first
- Dedupe near-identical stories
- Limit to ~20 items, with a soft rule to avoid 3-in-a-row from same source
- Write JSON to static/teams/{team}/items.json

This version includes:
- thumbnail enrichment with og:image / <img> fallback
- generic Google News thumbnail rejection
- stronger football filtering ("Week X Big Ten Preview", Ryan Walters, etc.)
"""

import os
import re
import json
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import requests
import feedparser
import yaml


# -------------------------------------------------------
# CONFIG / CONSTANTS
# -------------------------------------------------------

# how far back we’ll look (in hours) for “recent”
MAX_AGE_HOURS = 72  # ~3 days

# how many items we keep per team in final output
MAX_ITEMS = 20

# headers for HTTP requests to not get 403’d
FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PurdueHub/1.0; +https://example.invalid)"
}

# canonicalize source names (dedupe "GoldandBlack", "Gold and Black", etc.)
SOURCE_CANON = {
    "hammer & rails": "Hammer & Rails",
    "hammer and rails": "Hammer & Rails",
    "hammerandrails.com": "Hammer & Rails",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "jconline.com": "Journal & Courier",

    "goldandblack": "GoldandBlack (Rivals)",
    "gold and black": "GoldandBlack (Rivals)",
    "goldandblack.com": "GoldandBlack (Rivals)",
    "rivals.com": "GoldandBlack (Rivals)",  # we’ll stamp Rivals Purdue as that

    "on3": "On3 Purdue",
    "on3.com": "On3 Purdue",
    "on3purdue": "On3 Purdue",
    "on3 purdue": "On3 Purdue",

    "espn": "ESPN",
    "espn.com": "ESPN",

    "cbs sports": "CBS Sports",
    "cbssports.com": "CBS Sports",
    "247sports.com": "CBS Sports",  # 247 often gets syndicated under CBS Sports

    "yahoo sports": "Yahoo Sports",
    "sports.yahoo.com": "Yahoo Sports",
    "yahoo": "Yahoo Sports",

    "field of 68": "Field of 68",
    "youtube.com": "Field of 68",  # Field of 68 pods / YouTube uploads

    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",
}

# simple regexes for thumbnails
IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# detect obvious Google News / generic thumbs we want to ignore
def looks_like_generic_google_thumb(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    # very broad "this looks like a google-proxy thumbnail, not real art"
    if "gstatic.com" in u:
        return True
    if "googleusercontent.com" in u:
        return True
    # fallback: the classic multicolor 'G' card we're seeing
    if "google-news" in u or "news.google" in u:
        return True
    return False


# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------

def canon_source(raw: str) -> str:
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())


def canonical_url(url: str) -> str:
    """
    Strip query + fragment for dedupe comparison.
    """
    if not url:
        return ""
    p = urlparse(url)
    # keep scheme, netloc, path only
    clean = (p.scheme, p.netloc, p.path, "", "", "")
    return urlunparse(clean)


def parse_date(entry) -> datetime:
    """
    Try a few places to pull a datetime from a feedparser entry.
    """
    # feedparser usually gives published_parsed / updated_parsed as time.struct_time
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    # fallback: now
    return datetime.now(timezone.utc)


def fetch_og_image(url: str) -> str | None:
    """
    Try to fetch the article HTML and extract og:image or first <img>.
    Silent failure on purpose (we don't want job to die over a bad thumb).
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
            candidate = m.group(1).strip()
            if candidate and not looks_like_generic_google_thumb(candidate):
                return candidate

        # 2) <img> fallback
        m2 = IMG_TAG_RE.search(html)
        if m2:
            candidate = m2.group(1).strip()
            if candidate and not looks_like_generic_google_thumb(candidate):
                return candidate

    except Exception:
        return None
    return None


def extract_thumb_from_entry(entry, summary_html: str | None) -> str | None:
    """
    Step 1: RSS media_content/media_thumbnail
    Step 2: <img> in summary
    (fetch_og_image() happens later if still empty)
    """
    # media_content / media_thumbnail
    media_blocks = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media_blocks, list) and media_blocks:
        cand = media_blocks[0].get("url")
        if cand and not looks_like_generic_google_thumb(cand):
            return cand

    # <img> in summary/description
    if summary_html:
        m = IMG_TAG_RE.search(summary_html)
        if m:
            cand = m.group(1)
            if cand and not looks_like_generic_google_thumb(cand):
                return cand

    return None


def normalize_item(source_name: str, entry) -> dict:
    """
    Convert raw feedparser entry -> our internal dict.
    """
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary_html = (entry.get("summary") or entry.get("description") or "")

    pub_dt = parse_date(entry)

    # first-pass thumbnail
    thumb = extract_thumb_from_entry(entry, summary_html)

    return {
        "source": canon_source(source_name),
        "title": title,
        "link": link,
        "date": pub_dt.isoformat(),  # UTC ISO8601
        "image": thumb or None,
    }


# -------------------------------------------------------
# RELEVANCE FILTERING
# -------------------------------------------------------

def looks_like_football(text: str) -> bool:
    """
    Try to weed out obvious football / football-adjacent content.
    We are being aggressive because user only wants Purdue MBB.
    """
    if not text:
        return False

    t = text.lower()

    # Strong football signals
    football_terms = [
        "football",
        "qb", "quarterback", "wide receiver", "running back", "linebacker",
        "touchdown", "kickoff", "defensive coordinator", "offensive coordinator",
        "ryan walters", "coach walters", "walters'", "walters says",
        "bowl game", "bowl bid",
        "bye week", "depth chart",
        "safety blitz", "third down", "3rd down",
        "spring game", "spring practice",
    ]

    for term in football_terms:
        if term in t:
            return True

    # Pattern: "Week X Big Ten Preview" style stuff.
    # That tends to be football game-week previews, not hoops.
   