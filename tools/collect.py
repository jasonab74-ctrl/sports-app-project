#!/usr/bin/env python3
import os, json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse
import feedparser, yaml

# ---------------------------------------------
# CONFIG
# ---------------------------------------------
MAX_ITEMS_PER_FEED = 60       # how many items to read per source
TOP_N = 20                    # how many to publish
MAX_AGE_HOURS = 72            # rolling window (~3 days)
TEAM_SLUG = "purdue-mbb"
OUT_PATH = f"static/teams/{TEAM_SLUG}/items.json"

FEED_HEADERS = {
    "User-Agent": "purdue-mbb-newsbot/1.0 (+github actions)"
}

SOURCE_CANON = {
    "hammer and rails": "Hammer & Rails",
    "hammer & rails": "Hammer & Rails",
    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "goldandblack": "GoldandBlack",
    "goldandblack.com": "GoldandBlack",
    "on3 purdue": "On3 Purdue",
    "on3.com": "On3 Purdue",
    "yahoo sports": "Yahoo Sports",
    "yahoo! sports": "Yahoo Sports",
    "cbs sports": "CBS Sports",
    "espn": "ESPN",
    "espn.com": "ESPN",
    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",
    "field of 68": "Field of 68",
    "fieldof68": "Field of 68",
}

# ---------------------------------------------
# HELPERS
# ---------------------------------------------

def canon_source(raw):
    if not raw:
        return "Unknown"
    return SOURCE_CANON.get(raw.strip().lower(), raw.strip())

def canonical_url(url):
    if not url:
        return ""
    p = urlparse(url)
    clean = p._replace(query="", fragment="")
    return urlunparse(clean)

def parse_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def looks_like_football(blob):
    terms = [
        "football", "quarterback", "qb", "touchdown",
        "wide receiver", "linebacker", "defensive coordinator",
        "ryan walters", "coach walters", "walters'"
    ]
    lower = blob.lower()
    return any(t in lower for t in terms)

def is_relevant_purdue(item):
    blob = f"{item.get('title','')} {item.get('summary','')}".lower()
    if not ("purdue" in blob or "boilermaker" in blob):
        return False
    if looks_like_football(blob):
        return False
    return True

def normalize_item(source, entry):
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary = (entry.get("summary") or entry.get("description") or "")[:400]
    pub_dt = parse_date(entry)
    return {
        "source": canon_source(source),
        "title": title,
        "link": link,
        "date": pub_dt.strftime("%b %d"),
        "published": pub_dt.isoformat(),
    }

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = canonical_url(it.get("link")) or it.get("title","").lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out

# ---------------------------------------------
# MAIN
# ---------------------------------------------

def main():
    with open("src/feeds.yaml", "r", encoding="utf-8") as f:
        feeds_by_team = yaml.safe_load(f)

    feeds = feeds_by_team.get(TEAM_SLUG, [])
    if not feeds:
        raise SystemExit(f"No feeds configured for {TEAM_SLUG}")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    raw = []

    for fd in feeds:
        name = fd.get("name", "Source")
        url = fd.get("url")
        if not url: 
            continue
        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)
        for e in parsed.entries[:MAX_ITEMS_PER_FEED]:
            item = normalize_item(name, e)
            try:
                dt = datetime.fromisoformat(item["published"])
            except Exception:
                dt = datetime.now(timezone.utc)
            if dt < cutoff:
                continue
            if not is_relevant_purdue(item):
                continue
            raw.append(item)

    raw.sort(key=lambda x: datetime.fromisoformat(x["published"]), reverse=True)
    clean = dedupe(raw)[:TOP_N]

    data = {
        "team": TEAM_SLUG,
        "updated": datetime.now(timezone.utc).isoformat(),
        "items": [{"source": i["source"], "title": i["title"], "link": i["link"], "date": i["date"]} for i in clean],
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] {len(clean)} items written → {OUT_PATH}")

if __name__ == "__main__":
    main()