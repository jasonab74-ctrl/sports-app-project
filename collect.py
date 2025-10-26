#!/usr/bin/env python3
import os, json, feedparser, yaml, hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

TEAM_SLUG = "purdue-mbb"
OUT_FILE = f"static/teams/{TEAM_SLUG}/items.json"

MAX_ITEMS_PER_FEED = 50
TOP_N = 20
MAX_AGE_HOURS = 72

USER_AGENT = "purdue-mbb-hub-bot/1.0 (+github actions)"

SOURCE_MAP = {
    "hammer & rails":         "Hammer & Rails",
    "hammerandrails.com":     "Hammer & Rails",
    "goldandblack":           "GoldandBlack",
    "purdue.rivals.com":      "GoldandBlack",
    "on3 purdue":             "On3 Purdue",
    "on3.com":                "On3 Purdue",
    "journal & courier":      "Journal & Courier",
    "jconline":               "Journal & Courier",
    "jconline.com":           "Journal & Courier",
    "yahoo sports":           "Yahoo Sports",
    "sports.yahoo.com":       "Yahoo Sports",
    "cbs sports":             "CBS Sports",
    "cbssports.com":          "CBS Sports",
    "espn":                   "ESPN",
    "espn.com":               "ESPN",
    "purduesports":           "PurdueSports",
    "purduesports.com":       "PurdueSports",
    "field of 68":            "Field of 68",
    "youtube.com":            "Field of 68",
    "btn":                    "BTN",
    "btn.com":                "BTN",
    "big ten network":        "BTN",
}

def canon_source(raw: str) -> str:
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    if key in SOURCE_MAP:
        return SOURCE_MAP[key]
    host = key.replace("www.", "")
    if host in SOURCE_MAP:
        return SOURCE_MAP[host]
    return raw.strip()

def canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        clean = p._replace(fragment="", query="")
        return urlunparse(clean)
    except Exception:
        return url

def parse_date(entry):
    dt_struct = (
        getattr(entry, "published_parsed", None)
        or getattr(entry, "updated_parsed", None)
        or getattr(entry, "created_parsed", None)
    )
    if not dt_struct:
        return datetime.now(timezone.utc)
    return datetime(*dt_struct[:6], tzinfo=timezone.utc)

def normalize_item(source_name: str, entry) -> dict:
    link = getattr(entry, "link", "") or ""
    title = getattr(entry, "title", "") or ""
    pub_dt = parse_date(entry)
    return {
        "source": canon_source(source_name),
        "title": title.strip(),
        "link": canonical_url(link),
        "date": pub_dt.isoformat()
    }

def collect_items(feeds, cutoff_dt):
    items = []
    for fd in feeds:
        name = fd.get("name", "Unknown")
        url = fd.get("url", "")
        if not url:
            continue
        parsed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
        for e in parsed.entries[:MAX_ITEMS_PER_FEED]:
            it = normalize_item(name, e)
            try:
                dt_obj = datetime.fromisoformat(it["date"])
            except Exception:
                dt_obj = datetime.now(timezone.utc)
            if dt_obj < cutoff_dt:
                continue
            items.append(it)
    return items

def dedupe_and_sort(items):
    seen = set()
    uniq = []
    for it in items:
        key = hashlib.sha256((it["link"] + "|" + it["title"]).encode("utf-8","ignore")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    uniq.sort(key=lambda x: x["date"], reverse=True)
    return uniq[:TOP_N]

def main():
    with open("src/feeds.yaml","r",encoding="utf-8") as f:
        feeds_cfg = yaml.safe_load(f)
    feeds = feeds_cfg.get(TEAM_SLUG, [])
    if not feeds:
        raise SystemExit(f"No feeds configured for {TEAM_SLUG}")

    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    items = collect_items(feeds, cutoff_dt)
    items = dedupe_and_sort(items)

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE,"w",encoding="utf-8") as f:
        json.dump({"items": items}, f, indent=2)

    print(f"Wrote {len(items)} items -> {OUT_FILE}")

if __name__ == "__main__":
    main()
