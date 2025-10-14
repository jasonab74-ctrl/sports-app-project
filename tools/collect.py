#!/usr/bin/env python3
import json, sys, argparse, time, re
from datetime import datetime, timezone
from dateutil import parser as dtp
import feedparser
import requests

# ---- SOURCES (lightweight + stable) -----------------------------------------
OFFICIAL_FEEDS = [
    # Purdue official site – MBB category feed (works as a general athletics feed; we filter by hoops terms)
    "https://purduesports.com/rss.aspx?path=mbball",
]

INSIDER_FEEDS = [
    "https://www.hammerandrails.com/rss/index.xml",  # SB Nation Purdue
    # Add Journal & Courier’s Purdue feed if desired (many outlets block; keep to RSS)
]

NATIONAL_FEEDS = [
    # National CBB outlets that often mention Purdue (their team tags vary; we filter)
    "https://www.espn.com/espn/rss/ncb/news",     # ESPN CBB news
    "https://sports.yahoo.com/college-basketball/rss.xml",  # Yahoo CBB
    "https://www.cbssports.com/college-basketball/feeds/rss/main",  # CBS CBB
]

# ---- KEYWORD FILTERS ---------------------------------------------------------
# Keep this broad enough so we don’t starve the feed.
TEAM_TERMS = [
    r"\bPurdue\b",
    r"\bBoilermakers?\b",
    r"\bPainter\b", r"\bZach\s+Edey\b", r"\bBraden\s+Smith\b",
    r"\bMackey\s+Arena\b",
]

# Exclude football to avoid bleed-over:
EXCLUDE_TERMS = [
    r"\bfootball\b", r"\bgridiron\b",
]

TEAM_RE = re.compile("|".join(TEAM_TERMS), re.IGNORECASE)
EXCLUDE_RE = re.compile("|".join(EXCLUDE_TERMS), re.IGNORECASE)

# ---- HELPERS -----------------------------------------------------------------
def to_iso(ts):
    """Return strict ISO8601 with Z, falling back to now if missing."""
    if not ts:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = dtp.parse(ts)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()

def classify(url, source_title):
    host = (url or "").lower()
    src = (source_title or "").lower()
    if "purduesports.com" in host or "purduesports" in src:
        return "official"
    if "hammerandrails" in host or "journal" in src:
        return "insiders"
    # default to national if it got through the Purdue filter
    return "national"

def pick_image(entry):
    # Try common fields across feeds
    # feedparser puts images in media_content / links / summary with <img>
    if hasattr(entry, "media_content"):
        for mc in entry.media_content:
            if "url" in mc:
                return mc["url"]
    if hasattr(entry, "media_thumbnail"):
        for mt in entry.media_thumbnail:
            if "url" in mt:
                return mt["url"]
    if hasattr(entry, "links"):
        for ln in entry.links:
            if ln.get("rel") in ("enclosure", "image") and "href" in ln:
                return ln["href"]
    # last resort: scan summary for img src
    summ = getattr(entry, "summary", "") or ""
    m = re.search(r'<img[^>]+src="([^"]+)"', summ, re.IGNORECASE)
    if m:
        return m.group(1)
    return None

def acceptable(title, summary):
    blob = " ".join([title or "", summary or ""])
    if EXCLUDE_RE.search(blob):
        return False
    return bool(TEAM_RE.search(blob))

def harvest(feeds):
    items = []
    for url in feeds:
        try:
            d = feedparser.parse(url)
            for e in d.entries:
                title = getattr(e, "title", "")
                summary = getattr(e, "summary", "")
                link = getattr(e, "link", "")
                if not acceptable(title, summary):
                    continue
                published_raw = getattr(e, "published", "") or getattr(e, "updated", "")
                published = to_iso(published_raw)
                img = pick_image(e)
                source_title = getattr(d.feed, "title", "") or ""
                cat = classify(link, source_title)
                items.append({
                    "title": title,
                    "url": link,
                    "publishedAt": published,   # strict ISO for UI
                    "source": source_title,
                    "category": cat,            # official | insiders | national
                    "image": img
                })
        except Exception:
            continue
    # newest first
    items.sort(key=lambda x: x["publishedAt"], reverse=True)
    return items

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--news", action="store_true")
    ap.add_argument("--beat", action="store_true")
    args = ap.parse_args()

    if args.news or args.beat:
        news = harvest(OFFICIAL_FEEDS + INSIDER_FEEDS + NATIONAL_FEEDS)
        # de-dup by URL
        seen = set()
        uniq = []
        for n in news:
            if n["url"] in seen:
                continue
            seen.add(n["url"])
            uniq.append(n)
        # cap for UI headroom (store more than 10 so filters can slice)
        write_json("static/data/news.json", uniq[:50])

    if args.beat:
        # Beat = insiders first; if fewer than 6, top up with official items
        data = []
        try:
            with open("static/data/news.json", "r", encoding="utf-8") as f:
                all_news = json.load(f)
        except Exception:
            all_news = []

        insiders = [n for n in all_news if n.get("category") == "insiders"]
        official  = [n for n in all_news if n.get("category") == "official"]
        pick = insiders[:8] + official[:4]
        write_json("static/data/beat_links.json", pick[:10])

if __name__ == "__main__":
    main()