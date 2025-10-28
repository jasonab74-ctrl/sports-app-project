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
    "painter",
    "matt painter",
    "braden smith",
    "zach edey",
    "trey kaufman-renn",
    "fletcher loyer",
    "mason gillis",
    "mbb",
    "men's basketball",
    "men’s basketball",
    "exhibition",
    "scrimmage",
    "kentucky",
    "rupp arena",
]

GENERAL_PURDUE_TERMS = [
    "purdue",
    "boilermakers",
    "boilermaker",
    "mackey arena",
    "purdue athletics",
    "purdue mbb",
    "boiler ball",
]

# obvious non-hoops sports; we DOWNWEIGHT
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


def short_date_from_ts(epoch_sec):
    """
    Given epoch seconds, return e.g. 'Oct 27'.
    If 0 or invalid, return 'Just now' so frontend never sees ''.
    """
    if epoch_sec and epoch_sec > 0:
        try:
            d = datetime.datetime.fromtimestamp(epoch_sec)
            return d.strftime("%b %d")
        except Exception:
            pass
    return "Just now"


def fetch_feed(url, display_name):
    """
    Fetch and normalize items from either RSS/Atom or (if not RSS) HTML page.
    Returns a list of dicts:
    {
        "title": ...,
        "summary": ...,
        "link": ...,
        "published_ts": <epoch seconds>,
        "published_human": "Oct 27" (or "Just now"),
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

            published_ts = 0
            published_ts = max(
                published_ts,
                parse_date_struct(e.get("published_parsed")),
                parse_date_struct(e.get("updated_parsed")),
            )

            out.append({
                "title": title,
                "summary": summary,
                "link": link,
                "published_ts": published_ts,
                "published_human": short_date_from_ts(published_ts),
                "source": display_name,
            })
        return out

    # If it's not RSS, basic HTML scrape fallback
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # look for <article>, fallback to <a>
        articles = soup.find_all("article")
        if not articles:
            articles = soup.select("a")

        for a in articles:
            headline = ""
            teaser = ""
            link = ""

            if hasattr(a, "get_text"):
                headline = (a.get_text(separator=" ", strip=True) or "").strip()

            if hasattr(a, "get"):
                link = a.get("href") or ""
                if link.startswith("/"):
                    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(url))
                    link = base + link

            # skip garbage
            if len(headline.split()) < 3 or not link:
                continue

            out.append({
                "title": headline,
                "summary": teaser,
                "link": link,
                "published_ts": 0,
                "published_human": short_date_from_ts(0),
                "source": display_name,
            })

    except Exception:
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

    # downweight obvious non-hoops sports
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
    if ("goldandblack" in src
        or "on3" in src
        or "247sports" in src
        or "247 sports" in src):
        # heavy Purdue recruiting / beat coverage
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


def ensure_nonempty_payload(payload):
    """
    Safety: if we somehow ended up with [], create a single debug card.
    This prevents the frontend from ever rendering 'No recent stories found.'
    and tells us clearly that collector ran but filtering killed everything.
    """
    if payload:
        return payload
    return [{
        "title": "No Purdue MBB stories matched filters",
        "summary": "Collector ran successfully but strict filters removed everything. This is a fallback card.",
        "link": "",
        "published": "Just now",
        "source": "Collector Debug",
    }]


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

    # 5. Sort newest -> oldest, tiebreak by score
    def sort_key(it):
        return (it["published_ts"], it["score"])
    all_items.sort(key=sort_key, reverse=True)

    # 6. Primary filter: score >= 1
    filtered = [it for it in all_items if it["score"] >= 1]

    # 7. Fallback filter if primary is empty
    if not filtered:
        fallback = []
        for it in all_items:
            text = (it["title"] + " " + it["summary"]).lower()
            src = it.get("source", "").lower()
            if (
                "purdue" in text
                or "boilermaker" in text
                or "boilermakers" in text
                or "purdue" in src
                or "boilermaker" in src
                or "boilermakers" in src
            ):
                fallback.append(it)

        if fallback:
            filtered = fallback
        else:
            # final desperation fallback = everything
            filtered = all_items

    # 8. Truncate to top MAX_ITEMS
    filtered = filtered[:MAX_ITEMS]

    # 9. Prepare final shape for frontend
    final_payload = []
    for it in filtered:
        final_payload.append({
            "title": it["title"],
            "summary": it["summary"],
            "link": it["link"],
            # ALWAYS provide published string, never ""
            "published": it.get("published_human") or "Just now",
            "source": it["source"],
        })

    # 10. Safety: never write an empty array
    final_payload = ensure_nonempty_payload(final_payload)

    # 11. Write items.json
    ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ITEMS_PATH.open("w") as f:
        json.dump(final_payload, f, indent=2)

    print(f"Wrote {len(final_payload)} items to {ITEMS_PATH}")


if __name__ == "__main__":
    main()