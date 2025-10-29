#!/usr/bin/env python3

import os, json, feedparser, yaml
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

# =========================================
# SETTINGS
# =========================================

TEAM_SLUG = "purdue-mbb"

OUT_FILE = f"static/teams/{TEAM_SLUG}/items.json"

MAX_ITEMS_PER_FEED = 50      # how deep we pull from each feed
TOP_N = 40                   # how many total we keep before trim/filter
MAX_AGE_HOURS = 96           # rolling window (last ~4 days)

FEED_HEADERS = {
    "User-Agent": "purdue-mbb-bot/1.0 (+github pages scraper)"
}

# Canonical display names for source labels in UI
SOURCE_MAP = {
    "hammer & rails": "Hammer & Rails",
    "hammerandrails.com": "Hammer & Rails",

    "purduesports": "PurdueSports",
    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",

    "espn": "ESPN",
    "espn.com": "ESPN",

    "goldandblack": "GoldandBlack",
    "gold and black": "GoldandBlack",
    "goldandblack.com": "GoldandBlack",
    "rivals": "GoldandBlack",
    "purdue.rivals.com": "GoldandBlack",

    "on3": "On3 Purdue",
    "on3.com": "On3 Purdue",
    "on3 purdue": "On3 Purdue",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "j&c": "Journal & Courier",
    "jconline": "Journal & Courier",
    "jconline.com": "Journal & Courier",

    "cbs sports": "CBS Sports",
    "cbssports.com": "CBS Sports",
    "cbs sports college basketball": "CBS Sports",

    "yahoo sports": "Yahoo Sports",
    "sports.yahoo.com": "Yahoo Sports",
}

# =========================================
# HELPERS
# =========================================

def canon_source(raw_name: str) -> str:
    if not raw_name:
        return "Unknown"
    key = raw_name.strip().lower()
    # attempt 1: raw_name directly
    if key in SOURCE_MAP:
        return SOURCE_MAP[key]
    # attempt 2: look at domain
    try:
        host = urlparse(raw_name).netloc.lower()
        if host in SOURCE_MAP:
            return SOURCE_MAP[host]
    except Exception:
        pass
    return raw_name.strip()

def canonical_url(u: str) -> str:
    """strip tracking junk we don't care about"""
    if not u:
        return ""
    try:
        p = urlparse(u)
        clean = p._replace(query="", fragment="")
        return urlunparse(clean)
    except Exception:
        return u

def parse_date(entry):
    """
    Tries published_parsed / updated_parsed / etc.
    Falls back to now() if missing.
    Returns timezone-aware UTC datetime.
    """
    dt = None
    for cand in ["published_parsed", "updated_parsed", "created_parsed"]:
        if cand in entry and entry[cand]:
            dt = entry[cand]
            break
    if dt:
        return datetime(*dt[:6], tzinfo=timezone.utc)

    # fallback: now
    return datetime.now(timezone.utc)

def looks_like_purdue_mbb(title: str, summary: str, source_label: str) -> bool:
    """
    VERY IMPORTANT FILTER.
    We only want Purdue men's basketball, Purdue hoops recruiting,
    national men's college hoops w/ Purdue mention, etc.
    We want to drop volleyball / football / women's hoops / softball.
    """

    blob = f"{title} {summary} {source_label}".lower()

    # must mention some Purdue-ish + hoops-ish thing
    purdue_terms = [
        "purdue",
        "boilermaker",
        "boilermakers",
        "west lafayette",
        "#1 purdue",
        "boilers",
    ]

    hoops_terms = [
        "basketball",
        "men's basketball",
        "men’s basketball",
        "mbb",
        "big ten",
        "big ten basketball",
        "ncaa basketball",
        "guard",
        "forward",
        "center",
        "point guard",
        "shooting guard",
        "recruiting",
        "commit",
        "exhibition",
        "painter",        # Matt Painter
        "matt painter",
    ]

    # obvious "nope" words: volleyball, football, soccer, etc.
    reject_terms = [
        "volleyball",
        "football",
        "soccer",
        "softball",
        "baseball",
        "wrestling",
        "women's basketball",
        "women’s basketball",
        "wbb",
        "nil deal",
        "weekly awards",    # lots of generic dept PR
    ]

    # quick reject
    for bad in reject_terms:
        if bad in blob:
            return False

    # require at least one purdue-ish word
    if not any(t in blob for t in purdue_terms):
        # BUT allow high-value national hoops preview if Purdue clearly implied in title
        # e.g. "Men's college basketball megapreview, predictions for this season"
        # from ESPN could still matter because it's national context.
        # We'll allow that if it's clearly hoops and from a national source.
        if source_label.lower() in ["espn", "cbs sports", "yahoo sports"]:
            if any(h in blob for h in hoops_terms):
                return True
        return False

    # require at least one hoops-ish word
    if not any(t in blob for t in hoops_terms):
        return False

    return True


def normalize_item(source_name: str, entry) -> dict:
    title = (entry.get("title") or "").strip()
    link = entry.get("link") or ""
    link = canonical_url(link)
    summary = (entry.get("summary") or "")  # raw html sometimes
    pub_dt = parse_date(entry)
    source_label = canon_source(source_name)

    return {
        "source": source_label,
        "title": title,
        "link": link,
        # store ISO so JS can parse and format
        "date": pub_dt.isoformat()
    }


def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = (it["title"], it["source"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


# =========================================
# MAIN
# =========================================

def main():
    # load feeds
    with open("src/feeds.yaml", "r", encoding="utf-8") as f:
        all_cfg = yaml.safe_load(f)

    feeds = all_cfg.get(TEAM_SLUG, [])
    if not feeds:
        raise SystemExit(f"No feeds configured for {TEAM_SLUG}")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    collected = []

    for fd in feeds:
        name = fd.get("name", "Unknown Source")
        url = fd.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        for e in parsed.entries[:MAX_ITEMS_PER_FEED]:
            item = normalize_item(name, e)

            # convert ISO to dt for freshness
            try:
                pub_dt = datetime.fromisoformat(item["date"])
            except Exception:
                pub_dt = datetime.now(timezone.utc)

            # drop if too old
            if pub_dt < cutoff:
                continue

            # apply Purdue MBB relevance filter
            if not looks_like_purdue_mbb(item["title"], e.get("summary", ""), item["source"]):
                continue

            collected.append(item)

    # dedupe and sort newest first
    collected = dedupe(collected)
    collected.sort(key=lambda x: x["date"], reverse=True)

    # trim to ~20 for UI clarity
    trimmed = collected[:20]

    # final write
    os.makedirs(f"static/teams/{TEAM_SLUG}", exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "items": trimmed,
                "sources": sorted({it["source"] for it in collected})
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"Wrote {len(trimmed)} items to {OUT_FILE}")


if __name__ == "__main__":
    main()