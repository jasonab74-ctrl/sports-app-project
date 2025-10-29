#!/usr/bin/env python3

import os, json, feedparser, yaml
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

# =========================================================
# SETTINGS
# =========================================================

TEAM_SLUG = "purdue-mbb"

# where we write the final JSON that the site reads
OUT_FILE = f"static/teams/{TEAM_SLUG}/items.json"

# pull up to this many recent items per feed source
MAX_ITEMS_PER_FEED = 50

# publish at most this many items total on the page
TOP_N = 20

# rolling freshness window (hours)
MAX_AGE_HOURS = 72  # ~3 days

# polite fetch header
FEED_HEADERS = {
    "User-Agent": "purdue-mbb-bot/1.0 (github actions; Purdue MBB news aggregator)"
}

# canonical, nice display names for sources
SOURCE_MAP = {
    "hammer and rails": "Hammer & Rails",
    "hammer & rails": "Hammer & Rails",

    "goldandblack": "GoldandBlack",
    "goldandblack.com": "GoldandBlack",

    "on3 purdue": "On3 Purdue",
    "on3.com": "On3 Purdue",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "journalandcourier": "Journal & Courier",
    "jconline": "Journal & Courier",

    "yahoo sports": "Yahoo Sports",
    "yahoo! sports": "Yahoo Sports",

    "cbs sports": "CBS Sports",
    "cbssports.com": "CBS Sports",

    "espn": "ESPN",
    "espn.com": "ESPN",

    "purduesports": "PurdueSports",
    "purduesports.com": "PurdueSports",

    # you can add more aliases here if we add feeds later
}


# =========================================================
# HELPERS
# =========================================================

def canon_source(raw: str) -> str:
    """
    Normalize the source string coming from feed metadata.
    """
    if not raw:
        return "Unknown"
    return SOURCE_MAP.get(raw.strip().lower(), raw.strip())


def canonical_url(url: str) -> str:
    """
    Strip tracking junk etc. Return a clean URL.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # drop query + fragment to make links cleaner
        cleaned = parsed._replace(query="", fragment="")
        return urlunparse(cleaned)
    except Exception:
        return url


def parse_date(entry) -> datetime:
    """
    Try multiple fields from feedparser entry and fall back to 'now'.
    Always return timezone-aware UTC datetime.
    """
    candidates = [
        getattr(entry, "published_parsed", None),
        getattr(entry, "updated_parsed", None),
        getattr(entry, "created_parsed", None),
    ]

    for struct_t in candidates:
        if struct_t:
            # struct_time -> aware UTC datetime
            return datetime(*struct_t[:6], tzinfo=timezone.utc)

    # if nothing, just use now so it doesn't get dropped
    return datetime.now(timezone.utc)


def looks_like_football(blob: str) -> bool:
    """
    Heuristic: filter obvious football-only stories.
    We KEEP men's basketball. We DROP football.
    """
    terms = [
        "football",
        "quarterback",
        "qb",
        "touchdown",
        "wide receiver",
        "linebacker",
        "defensive coordinator",
        "defensive backs coach",
        "field goal",
        "ryan walters",    # Purdue football head coach
        "coach walters",
        "walters said",
    ]
    b = blob.lower()
    return any(t in b for t in terms)


def is_relevant_purdue(item) -> bool:
    """
    Decide if a story is about Purdue men's basketball (or close enough).
    We allow 'Purdue', 'Boilermakers', 'basketball', 'Painter', etc.
    We reject obvious football-only hits.
    """
    blob = f"{item.get('title','')} {item.get('summary','')}".lower()

    # auto-keep if it clearly sounds like hoops
    if (
        "basketball" in blob
        or "painter" in blob          # Matt Painter quotes and postgame
        or "boilermakers" in blob     # generic team nickname
        or "mbb" in blob              # sometimes writers actually tag it like this
    ):
        # but still block if football-y
        if looks_like_football(blob):
            return False
        return True

    # fallback: keep if it even says "purdue"
    if "purdue" in blob:
        if looks_like_football(blob):
            return False
        return True

    # otherwise drop it
    return False


def normalize_item(source_name: str, entry) -> dict:
    """
    Convert 1 RSS/Atom entry from feedparser into our standard dict.
    """
    link = entry.get("link", "") or ""
    title = (entry.get("title", "") or "").strip()
    summary = entry.get("summary", "") or ""

    pub_dt = parse_date(entry)

    return {
        "source": canon_source(source_name),
        "title": title,
        "summary": summary,
        "link": canonical_url(link),
        "date": pub_dt.isoformat(),  # always store ISO8601 string
    }


def dedupe(items: list[dict]) -> list[dict]:
    """
    Deduplicate by (source,title,link) so we don't show the same post
    repeated in slightly different feeds.
    """
    seen = set()
    out = []
    for it in items:
        key = (it["source"], it["title"], it["link"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


# =========================================================
# MAIN
# =========================================================

def main():
    # load feed list from src/feeds.yaml
    with open("src/feeds.yaml", "r", encoding="utf-8") as f:
        feeds = yaml.safe_load(f).get(TEAM_SLUG, [])

    if not feeds:
        raise SystemExit(f"No feeds found for {TEAM_SLUG} in src/feeds.yaml")

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

            # date check (freshness)
            try:
                dt = datetime.fromisoformat(item["date"])
            except Exception:
                # if somehow busted date, keep it anyway (rare)
                dt = datetime.now(timezone.utc)

            if dt < cutoff:
                continue

            # relevance check
            if not is_relevant_purdue({
                "title": item["title"],
                "summary": item["summary"],
            }):
                continue

            collected.append(item)

    # sort newest first
    collected.sort(key=lambda x: x["date"], reverse=True)

    # take top N
    top = collected[:TOP_N]

    # write for frontend
    payload = {
        "updated_ts": datetime.now(timezone.utc).isoformat(),
        "items": top,
    }

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {len(top)} stories to {OUT_FILE}")


if __name__ == "__main__":
    main()