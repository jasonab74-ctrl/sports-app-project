#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Collector: Purdue MBB
 - Reads feeds from static/sources.json
 - Filters to Purdue *Men's Basketball* only
 - Scores / ranks items, sorts DESC by published, keeps top 20
 - Writes static/teams/purdue-mbb/items.json
"""

import json, os, re, time, hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(__file__))  # repo root
OUT_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
OUT_FILE = os.path.join(OUT_DIR, "items.json")
SRC_FILE = os.path.join(ROOT, "static", "sources.json")
WIDGETS_FILE = os.path.join(ROOT, "static", "widgets.json")

os.makedirs(OUT_DIR, exist_ok=True)

# --- Helpers -----------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat()

def to_iso(dt_struct, fallback=None):
    try:
        if isinstance(dt_struct, time.struct_time):
            return datetime.fromtimestamp(time.mktime(dt_struct), tz=timezone.utc).astimezone().isoformat()
    except Exception:
        pass
    return fallback or now_iso()

def clean(text):
    if not text: return ""
    # de-entity & de-whitespace
    return re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text()).strip()

def hostname(url):
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""

# --- Filtering logic ----------------------------------------------------------

NEGATIVE = re.compile(
    r"\b(football|volleyball|soccer|wrestling|baseball|softball|women'?s|wbb|recruiting visit|nfl|mlb|ncaaf)\b",
    re.I
)
PURDUE = re.compile(r"\bpurdue\b", re.I)
BASKET = re.compile(r"\b(men'?s\s+)?basketball|mbb|boilermakers\b", re.I)

def score_item(title, summary, link, source_hint=""):
    t = f"{title} {summary} {source_hint} {link}"
    t_clean = clean(t).lower()

    if NEGATIVE.search(t_clean):
        return -10

    s = 0
    if PURDUE.search(t_clean): s += 4
    if BASKET.search(t_clean): s += 4
    # prefer strong sources a bit
    host = hostname(link)
    if host:
        if "purduesports.com" in host: s += 2
        if "yahoo." in host or "espn." in host or "cbs" in host or "si.com" in host: s += 1

    # de-dup googly junk
    if "/video" in link or "/podcast" in link: s -= 1

    return s

# --- Load config --------------------------------------------------------------

with open(SRC_FILE, "r", encoding="utf-8") as f:
    SRC = json.load(f)
with open(WIDGETS_FILE, "r", encoding="utf-8") as f:
    WCFG = json.load(f)

LIMIT = int(WCFG.get("limit", 20))
HOURS_BACK = int(WCFG.get("hours_back", 240))  # look back window
CUTOFF = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

FEEDS = SRC.get("feeds", [])

# --- Collect -----------------------------------------------------------------

items = []
seen = set()

for feed_url in FEEDS:
    try:
        d = feedparser.parse(feed_url)
        for e in d.entries[:60]:
            title = clean(e.get("title", ""))
            summary = clean(e.get("summary", "") or e.get("description", ""))
            link = e.get("link") or ""
            if not link: continue

            # published
            published = None
            if getattr(e, "published_parsed", None):
                published = to_iso(e.published_parsed)
            elif getattr(e, "updated_parsed", None):
                published = to_iso(e.updated_parsed)
            else:
                published = now_iso()

            # skip stale
            try:
                if datetime.fromisoformat(published).astimezone(timezone.utc) < CUTOFF:
                    continue
            except Exception:
                pass

            key = hashlib.md5((title + link).encode("utf-8")).hexdigest()
            if key in seen: continue
            seen.add(key)

            src_host = hostname(link)
            source = e.get("source", {}).get("title") or d.feed.get("title") or (src_host or "Source")

            s = score_item(title, summary, link, source)
            if s < 6:  # tightened threshold to reduce off-topic
                continue

            items.append({
                "title": title,
                "summary": summary,
                "url": link,
                "published": published,
                "source": source,
                "score": s
            })
    except Exception:
        continue

# sort newest → oldest; then score
def _sort_key(it):
    try:
        ts = datetime.fromisoformat(it["published"]).timestamp()
    except Exception:
        ts = 0
    return (ts, it.get("score", 0))

items.sort(key=_sort_key, reverse=True)
items = items[:LIMIT]

out = {
    "team": "purdue-mbb",
    "updated": now_iso(),
    "count": len(items),
    "items": items
}

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"Wrote {len(items)} items → {OUT_FILE}")