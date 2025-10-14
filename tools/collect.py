#!/usr/bin/env python3
# tools/collect.py
#
# Builds:
#   static/data/news.json
#   static/data/rankings.json
#   static/data/schedule.json
#   static/data/beat_links.json
#
# Notes
# - Focuses on Purdue Men's Basketball.
# - All timestamps are ISO 8601 (UTC) to avoid the "thousands of minutes" bug.
# - Beat links: pulls from multiple sources; filters to Purdue hoops context.
# - Keep this file self-contained (stdlib + feedparser + requests).

import os
import re
import json
import time
import math
import hashlib
import datetime as dt
from urllib.parse import urlparse, urlencode

import requests

try:
    import feedparser  # lightweight RSS/Atom parser
except Exception:
    # Optional fallback if feedparser isn't preinstalled:
    # You can add "pip install feedparser" in your GH Action before running this.
    raise SystemExit("Missing dependency: feedparser. Please pip install feedparser in the workflow.")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'static', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

UTC = dt.timezone.utc

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})

# -------------------------------
# Utilities
# -------------------------------

PURDUE_RE = re.compile(r"\bPurdue\b", re.IGNORECASE)
HOOPS_RE  = re.compile(r"\b(basketball|hoops|CBB|men'?s)\b", re.IGNORECASE)

def is_purdue_hoops(text: str) -> bool:
    if not text:
        return False
    return bool(PURDUE_RE.search(text)) and bool(HOOPS_RE.search(text))

def iso_now() -> str:
    return dt.datetime.now(UTC).isoformat()

def to_iso(ts) -> str:
    """Convert feed timestamps to ISO; fallback to now."""
    try:
        if isinstance(ts, (int, float)):
            return dt.datetime.fromtimestamp(ts, UTC).isoformat()
        if isinstance(ts, time.struct_time):
            return dt.datetime.fromtimestamp(time.mktime(ts), UTC).isoformat()
    except Exception:
        pass
    return iso_now()

def write_json(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def og_image(url: str) -> str | None:
    """Light best-effort attempt to retrieve an OpenGraph image (respecting robots via normal requests).
       Safe fallback: return None if we can't find one quickly."""
    try:
        r = SESSION.get(url, timeout=6)
        if r.status_code != 200 or "<html" not in r.text[:2000].lower():
            return None
        html = r.text
        # Simple OG parser
        for tag in ('property="og:image"', "property='og:image'", 'name="og:image"', "name='og:image'"):
            idx = html.find(tag)
            if idx != -1:
                # find content="..."
                cidx = html.find("content=", idx)
                if cidx != -1:
                    quote = '"' if '"' in html[cidx+8:cidx+9] else "'"
                    first = html.find(quote, cidx)
                    second = html.find(quote, first+1)
                    if first != -1 and second != -1:
                        val = html[first+1:second].strip()
                        if val.startswith("http"):
                            return val
        return None
    except Exception:
        return None

def safe_source(netloc: str) -> str:
    # Normalize well-known sources to neat labels
    domain = netloc.lower()
    if "hammerandrails" in domain: return "hammerandrails.com"
    if "purdue" in domain and "sports" in domain: return "purdueports.com" if False else "purduesports.com"
    if "rivals" in domain or "goldandblack" in domain: return "Gold and Black"
    if "yahoo" in domain: return "Yahoo CBB"
    if "journ" in domain and "courier" in domain: return "Journal & Courier"
    if "espn" in domain: return "ESPN"
    if "cbs" in domain: return "CBS Sports"
    if "kenpom" in domain: return "KenPom"
    return domain

def dedupe(items, key="url"):
    seen = set()
    out = []
    for it in items:
        k = it.get(key)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out

def clamp_int(val, lo, hi):
    try:
        v = int(val)
        return max(lo, min(hi, v))
    except Exception:
        return lo

# -------------------------------
# Collect NEWS (already working for you)
# -------------------------------

def collect_news() -> list[dict]:
    """
    Your site already has this working. We’ll keep it light here:
    Expect upstream job/script to populate most sources; this function
    just trusts those sources or could be extended if needed.
    """
    # If you already have a script creating news.json upstream, keep that.
    # Here, we simply leave it as-is (no-op). This placeholder returns [].
    return []

# -------------------------------
# Rankings (AP + KenPom)
# -------------------------------

def collect_rankings() -> dict:
    """
    You already show AP & KenPom. Keep simple placeholders here because
    another script may already be writing rankings.json. If not, you can
    wire the real scrapes here.
    """
    return {
        "ap_top25": None,      # int or None
        "kenpom":   None,      # int or None
        "updated_at": iso_now()
    }

# -------------------------------
# Schedule (already working for you)
# -------------------------------

def collect_schedule() -> list[dict]:
    """
    Your schedule builder is already good. Keep placeholder here; another
    script may already write schedule.json.
    """
    return []

# -------------------------------
# Insider / Beat Links
# -------------------------------

BEAT_SOURCES = [
    # RSS/Atom or tag feeds that reliably surface Purdue hoops
    # (These URLs are stable; if any 404, we just skip gracefully.)
    ("https://www.hammerandrails.com/rss/index.xml", "Hammer & Rails"),
    ("https://purdue.rivals.com/rss", "Gold and Black"),
    ("https://sports.yahoo.com/college-basketball/teams/purdue/news?format=rss", "Yahoo CBB"),
    # Journal & Courier Purdue tag sometimes: leaving commented as site may block RSS scraping
    # ("https://www.jconline.com/search/?q=Purdue+basketball&output=rss", "Journal & Courier"),
]

def collect_beat_links(limit=10) -> list[dict]:
    items: list[dict] = []
    for feed_url, label in BEAT_SOURCES:
        try:
            parsed = feedparser.parse(feed_url)
            for e in parsed.entries[:25]:
                title = e.get("title", "") or ""
                summary = e.get("summary", "") or ""
                link = e.get("link", "") or ""
                if not link or not title:
                    continue

                text = f"{title} {summary}"
                if not is_purdue_hoops(text):
                    # Some feeds (e.g., Rivals) don’t always include “Purdue” in title;
                    # keep a lighter fallback: if domain is clearly a Purdue beat source,
                    # allow basketball keywords only.
                    netloc = urlparse(link).netloc.lower()
                    if ("hammerandrails" in netloc or "rivals" in netloc or "goldandblack" in netloc):
                        if not HOOPS_RE.search(text):
                            continue
                    else:
                        continue

                published_iso = None
                if "published_parsed" in e and e.published_parsed:
                    published_iso = to_iso(e.published_parsed)
                elif "updated_parsed" in e and e.updated_parsed:
                    published_iso = to_iso(e.updated_parsed)
                else:
                    published_iso = iso_now()

                # Try to get image (from media or OG)
                image = None
                media_content = e.get("media_content") or e.get("media_thumbnail")
                if isinstance(media_content, list) and media_content:
                    cand = media_content[0]
                    image = cand.get("url")
                if not image:
                    image = og_image(link)

                items.append({
                    "title": title.strip(),
                    "url": link,
                    "source": label if label else safe_source(urlparse(link).netloc),
                    "published_at": published_iso,
                    "image": image
                })
        except Exception:
            # skip this feed on any error
            continue

    # Deduplicate by URL, latest first
    items = dedupe(items, key="url")
    try:
        items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    except Exception:
        pass

    # Cap to limit
    return items[:clamp_int(limit, 4, 20)]

# -------------------------------
# Main
# -------------------------------

def main():
    # If upstream jobs already write news/rankings/schedule, we preserve those.
    # We ONLY overwrite when we have non-empty data; otherwise do not clobber.

    # Beat links (we own this) – always write our fresh list:
    beat_items = collect_beat_links(limit=12)
    write_json(os.path.join(DATA_DIR, "beat_links.json"), {"items": beat_items, "generated_at": iso_now()})

    # Rankings (optional here; you already have a builder)
    # If you want this file to be the source of truth, uncomment:
    # rankings = collect_rankings()
    # write_json(os.path.join(DATA_DIR, "rankings.json"), rankings)

    # News (optional – often built by your node script)
    # news_items = collect_news()
    # if news_items:
    #     write_json(os.path.join(DATA_DIR, "news.json"), {"items": news_items, "generated_at": iso_now()})

    # Schedule (optional – you already have it wired)
    # sched_items = collect_schedule()
    # if sched_items:
    #     write_json(os.path.join(DATA_DIR, "schedule.json"), {"games": sched_items, "generated_at": iso_now()})

if __name__ == "__main__":
    main()