#!/usr/bin/env python3
import os, json, feedparser, yaml
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

# SETTINGS
TEAM_SLUG = "purdue-mbb"

OUT_FILE = f"static/teams/{TEAM_SLUG}/items.json"

MAX_ITEMS_PER_FEED = 50
TOP_N = 20
MAX_AGE_HOURS = 72  # rolling ~3 days

FEED_HEADERS = {
    "User-Agent": "purdue-mbb-bot/1.0 (+github actions)"
}

# canonical mapping for source names
SOURCE_MAP = {
    "hammer and rails": "Hammer & Rails",
    "hammer & rails": "Hammer & Rails",

    "goldandblack": "GoldandBlack",
    "goldandblack.com": "GoldandBlack",

    "on3 purdue": "On3 Purdue",
    "on3.com": "On3 Purdue",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",

    "yahoo sports": "Yahoo Sports",
    "cbs sports": "CBS Sports",
    "espn": "ESPN",
    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports"
}

def canon_source(raw):
    if not raw:
        return "Unknown"
    return SOURCE_MAP.get(raw.strip().lower(), raw.strip())

def canonical_url(url):
    if not url:
        return ""
    parts = urlparse(url)
    # drop tracking junk etc (simple)
    clean = parts._replace(query="")
    return urlunparse(clean)

def parse_date(entry):
    # Try published_parsed first
    dt = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    else:
        # fallback: now
        dt = datetime.now(timezone.utc)
    return dt

def looks_like_football(blob: str) -> bool:
    """
    crude keyword filter to toss obvious football-only talk
    """
    terms = [
        "football",
        "quarterback",
        "qb",
        "touchdown",
        "wide receiver",
        "linebacker",
        "ryan walters",
        "coach walters",
        "walters",
        "defensive coordinator",
        "field goal",
    ]
    b = blob.lower()
    return any(t in b for t in terms)

def is_relevant_purdue(item) -> bool:
    # Only want Purdue men's basketball content.
    # We'll do a dumb include of "purdue" AND reject obvious football.
    blob = f"{item.get('title','')} {item.get('summary','')}"
    text = blob.lower()

    if "purdue" not in text:
        return False

    if looks_like_football(blob):
        return False

    # You could add "women's basketball" exclude etc here if needed.

    return True

def normalize_item(source, entry):
    link = entry.get("link", "") or ""
    title = (entry.get("title", "") or "").strip()
    summary = (entry.get("summary", "") or "").strip()

    pub_dt = parse_date(entry)

    return {
        "source": canon_source(source),
        "title": title,
        "summary": summary,
        "link": canonical_url(link),
        "date": pub_dt.isoformat(),
    }

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = (it["title"], it["link"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def main():
    # load feeds list from src/feeds.yml
    with open("src/feeds.yml", "r", encoding="utf-8") as f:
        feeds = yaml.safe_load(f).get(TEAM_SLUG, [])

    if not feeds:
        raise SystemExit(f"No feeds found for {TEAM_SLUG}")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    collected = []

    for fd in feeds:
        name = fd.get("name", "Unknown")
        url = fd.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        for e in parsed.entries[:MAX_ITEMS_PER_FEED]:
            item = normalize_item(name, e)

            # filter by staleness
            try:
                dt_obj = datetime.fromisoformat(item["date"])
            except ValueError:
                dt_obj = datetime.now(timezone.utc)

            if dt_obj < cutoff:
                continue

            if not is_relevant_purdue(item):
                continue

            collected.append(item)

    # sort newest first
    collected.sort(
        key=lambda it: datetime.fromisoformat(it["date"]),
        reverse=True
    )

    # dedupe & cap
    collected = dedupe(collected)
    top = collected[:TOP_N]

    payload = {
        "updated_ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "items": top
    }

    # ensure folder exists
    out_dir = os.path.dirname(OUT_FILE)
    os.makedirs(out_dir, exist_ok=True)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {len(top)} stories to {OUT_FILE}")

if __name__ == "__main__":
    main()