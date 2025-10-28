#!/usr/bin/env python3
"""
collect.py – Purdue Men's Basketball feed aggregator
---------------------------------------------------
Fetches news from Purdue + national sources, filters for Purdue or
men's basketball, dedupes, sorts newest→oldest, writes JSON for the site.
"""

import os, json, time, feedparser, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

###############################################################################
# SOURCES
###############################################################################

SOURCES = [
    {"name": "Purdue Athletics MBB", "url": "https://purduesports.com/rss?path=mbball"},
    {"name": "GoldandBlack.com", "url": "https://www.on3.com/teams/purdue-boilermakers/feed/"},
    {"name": "Yahoo Sports College Basketball", "url": "https://sports.yahoo.com/college-basketball/rss/"},
    {"name": "CBS Sports College Basketball", "url": "https://www.cbssports.com/college-basketball/rss/headlines/"},
    {"name": "ESPN College Basketball", "url": "https://www.espn.com/espn/rss/ncb/news"},
    {"name": "The Field of 68", "url": "https://thefieldof68.com/feed"},
    {"name": "SI Purdue", "url": "https://www.si.com/rss/college/purdue"},
    {"name": "USA Today Purdue", "url": "https://usatoday.com/sports/college/purdue/rss"},
]

###############################################################################
# FILTERING KEYWORDS
###############################################################################

POSITIVE = [
    "purdue", "boilermaker", "painter", "braden smith", "zach edey",
    "fletcher loyer", "trey kaufman", "purdue men's basketball",
    "purdue basketball", "mbb", "boilermakers", "matt painter"
]

NEGATIVE = [
    "football", "soccer", "volleyball", "baseball", "softball",
    "wrestling", "track", "swim", "cross country", "tennis", "golf"
]

###############################################################################
# HELPERS
###############################################################################

def clean(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(" ", strip=True).replace("&#39;", "'").replace("&quot;", '"')

def epoch_from_struct(s):
    try:
        if s: return int(time.mktime(s))
    except Exception:
        pass
    return 0

def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def short_date(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d")

###############################################################################
# FETCH + FILTER
###############################################################################

def fetch_feed(src):
    parsed = feedparser.parse(src["url"])
    items = []
    for e in parsed.entries:
        title = clean(getattr(e, "title", ""))
        summary = clean(getattr(e, "summary", getattr(e, "description", "")))
        link = getattr(e, "link", "")
        ts = epoch_from_struct(getattr(e, "published_parsed", getattr(e, "updated_parsed", None)))

        text = f"{title.lower()} {summary.lower()}"
        # keep if Purdue or basketball, skip if other sports
        if any(p in text for p in POSITIVE) and not any(n in text for n in NEGATIVE):
            items.append({
                "source": src["name"],
                "headline": title,
                "summary": summary,
                "url": link,
                "published_epoch": ts,
                "published": short_date(ts) if ts else "",
                "published_iso": iso(ts) if ts else "",
            })
    return items

###############################################################################
# MAIN
###############################################################################

def collect():
    all_items = []
    for src in SOURCES:
        try:
            items = fetch_feed(src)
            all_items.extend(items)
            print(f"{src['name']}: {len(items)}")
        except Exception as e:
            print(f"{src['name']} error: {e}")

    # dedupe by headline
    seen = set()
    unique = []
    for it in all_items:
        key = it["headline"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(it)

    # sort newest→oldest and take top 20
    unique.sort(key=lambda x: x.get("published_epoch", 0), reverse=True)
    final = unique[:20]

    out_path = os.path.join("static", "teams", "purdue-mbb")
    os.makedirs(out_path, exist_ok=True)
    out_file = os.path.join(out_path, "items.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"✅ Wrote {len(final)} items to {out_file}")

if __name__ == "__main__":
    collect()