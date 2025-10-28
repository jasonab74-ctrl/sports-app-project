#!/usr/bin/env python3

import json
import re
import time
import datetime
from urllib.parse import urlparse
import feedparser
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# -------- CONFIG --------

TEAM_SLUG = "purdue-mbb"

ROOT = Path(__file__).resolve().parents[1]  # repo root (project/)
ITEMS_PATH = ROOT / "static" / "teams" / TEAM_SLUG / "items.json"
SOURCES_PATH = ROOT / "static" / "teams" / TEAM_SLUG / "sources.json"

MAX_ITEMS = 20  # how many cards we keep

# Keywords / signals
STRONG_HOOPS_TERMS = [
    "purdue men's basketball",
    "purdue men’s basketball",
    "purdue men's hoops",
    "purdue men’s hoops",
    "boilermakers men's basketball",
    "boilermakers men’s basketball",
    "boilermakers hoops",
    "painter",           # Matt Painter
    "braden smith",
    "zach edey",
    "trey kaufman-renn",
    "fletcher loyer",
    "mason gillis",
    "big ten media day",
    "exhibition",        # preseason games/scrimmages
    "scrimmage",
    "kentucky",          # often tied to preseason scrimmage
    "rupp arena",
    "mbb",               # Purdue Athletics uses MBB
    "men's basketball",
    "men’s basketball"
]

GENERAL_PURDUE_TERMS = [
    "purdue",
    "boilermakers",
    "boilermaker",
    "mackey arena",
    "matt painter",
    "purdue athletics",
    "purdue mbb",
    "boiler ball",
]

# obvious non-hoops sports; we DOWNWEIGHT but we don't insta-kill
OTHER_SPORT_TERMS = [
    "football",
    "volleyball",
    "soccer",
    "wrestling",
    "baseball",
    "softball",
    "tennis",
    "golf",
    "track",
    "cross country",
]


def load_sources():
    with SOURCES_PATH.open() as f:
        return json.load(f)


def parse_date_struct(dt_struct):
    """
    feedparser gives published_parsed / updated_parsed as time.struct_time.
    Convert to epoch seconds. If not present, return 0 so it sorts last.
    """
    if not dt_struct:
        return 0
    try:
        return int(time.mktime(dt_struct))
    except Exception:
        return 0


def fetch_feed(url, display_name):
    """
    Fetch and normalize items from either RSS/Atom or (if not RSS) HTML page.
    Returns a list of dicts:
    {
        "title": ...,
        "summary": ...,
        "link": ...,
        "published_ts": <epoch seconds>,
        "published_human": "Oct 27",
        "source": display_name
    }
    """
    out = []

    # Try RSS first
    parsed = feedparser.parse(url)
    if parsed and parsed.entries:
        for e in parsed.entries:
            title = (e.get("title") or "").strip()
            summary = (e.get("summary") or e.get("description") or "").strip()

            link = (
                e.get("link")
                or e.get("id")
                or ""
            ).strip()

            # pick a date
            published_ts = 0
            published_ts = max(
                published_ts,
                parse_date_struct(e.get("published_parsed")),
                parse_date_struct(e.get("updated_parsed")),
            )

            # nice short date (e.g. "Oct 27")
            if published_ts:
                d = datetime.datetime.fromtimestamp(published_ts)
                published_human = d.strftime("%b %d")
            else:
                published_human = ""

            out.append({
                "title": title,
                "summary": summary,
                "link": link,
                "published_ts": published_ts,
                "published_human": published_human,
                "source": display_name,
            })
        return out

    # If it's not RSS, do a simple HTML scrape fallback.
    # We'll try to grab headlines off the page.
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # super simple heuristic: <article> blocks, or headline links
        articles = soup.find_all("article")
        if not articles:
            # fallback to links in main content
            articles = soup.select("a")

        for a in articles:
            # try to find a headline-ish text
            headline = ""
            teaser = ""
            link = ""

            if hasattr(a, "get_text"):
                headline = (a.get_text(separator=" ", strip=True) or "").strip()

            if hasattr(a, "get"):
                link = a.get("href") or ""
                if link.startswith("/"):
                    # make absolute
                    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(url))
                    link = base + link

            # basic sanity: must have some headline-like content and a link
            if len(headline.split()) < 3 or not link:
                continue

            # we don't have published timestamps from raw scrape; set 0
            out.append({
                "title": headline,
                "summary": teaser,
                "link": link,
                "published_ts": 0,
                "published_human": "",
                "source": display_name,
            })

    except Exception:
        # swallow network/parse errors for this source
        pass

    return out


def score_item(item):
    """
    Give each item a Purdue MBB relevance score.
    - Strong Purdue MBB language: big boost
    - General Purdue mentions: medium boost
    - Other sports keywords: penalty
    - Trusted Purdue sources: boost
    """
    t = f"{item['title']} {item['summary']}".lower()

    score = 0

    # strong hoops terms
    for kw in STRONG_HOOPS_TERMS:
        if kw in t:
            score += 3

    # general Purdue terms
    for kw in GENERAL_PURDUE_TERMS:
        if kw in t:
            score += 2

    # downweight obvious non-hoops sports if they appear
    for kw in OTHER_SPORT_TERMS:
        if kw in t:
            score -= 3

    # source boost if it's clearly Purdue men's basketball channel
    src = item.get("source", "").lower()
    if "purdue athletics mbb" in src:
        score += 4
    if "purdue" in src and "mbb" in src:
        score += 3
    if "purdue athletics" in src and "basketball" in t:
        score += 2
    if "goldandblack" in src or "on3" in src or "247sports" in src:
        # these guys cover Purdue hoops heavily
        score += 2

    return score


def dedupe(items):
    """
    Remove obvious duplicates by title+link.
    Keep the one with the most recent timestamp.
    """
    by_key = {}
    for it in items:
        key = (it["title"].strip().lower(), it["link"].strip().lower())
        prev = by_key.get(key)
        if not prev or it["published_ts"] > prev["published_ts"]:
            by_key[key] = it
    return list(by_key.values())


def main():
    # 1. Load sources
    sources = load_sources()  # list of {"name": "...", "url": "..."}
    all_items = []

    # 2. Aggregate raw items from each source
    for src in sources:
        name = src.get("name", "").strip()
        url = src.get("url", "").strip()
        if not url:
            continue

        fetched = fetch_feed(url, name)
        all_items.extend(fetched)

    # 3. De-dupe
    all_items = dedupe(all_items)

    # 4. Score relevance
    for it in all_items:
        it["score"] = score_item(it)

    # 5. Sort by published_ts desc first, then by score desc as tiebreak
    # (newest first is your requirement; score helps order within same timestamp)
    def sort_key(it):
        return (it["published_ts"], it["score"])
    all_items.sort(key=sort_key, reverse=True)

    # 6. Soft filter:
    # Keep anything with score >= 1
    filtered = [it for it in all_items if it["score"] >= 1]

    # 7. Fallback if we accidentally got too aggressive and killed everything
    if not filtered:
        # fallback strategy:
        # grab anything whose source looks like Purdue Athletics MBB
        fallback = [
            it for it in all_items
            if "purdue athletics" in it.get("source", "").lower()
            or "purdue" in it.get("source", "").lower()
        ]
        # if *that* is also empty, final fallback = just take newest 20 of everything
        filtered = fallback if fallback else all_items

    # 8. Truncate to top N
    filtered = filtered[:MAX_ITEMS]

    # 9. Prepare final shape for frontend
    final_payload = []
    for it in filtered:
        final_payload.append({
            "title": it["title"],
            "summary": it["summary"],
            "link": it["link"],
            "published": it["published_human"],  # short date like "Oct 27"
            "source": it["source"],
        })

    # 10. Write items.json
    ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ITEMS_PATH.open("w") as f:
        json.dump(final_payload, f, indent=2)

    print(f"Wrote {len(final_payload)} items to {ITEMS_PATH}")


if __name__ == "__main__":
    main()