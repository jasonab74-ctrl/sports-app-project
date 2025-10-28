#!/usr/bin/env python3
import os
import json
import time
import re
import hashlib
import requests
import feedparser
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ---------------------------
# CONFIG
# ---------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUTPUT_PATH = os.path.join(
    PROJECT_ROOT,
    "static",
    "teams",
    "purdue-mbb",
    "items.json"
)

SOURCES_PATH = os.path.join(
    PROJECT_ROOT,
    "static",
    "teams",
    "purdue-mbb",
    "sources.json"
)

# Words that mean "this is actually about Purdue men's hoops"
PURDUE_KEYWORDS = [
    "purdue",
    "boilermakers",
    "matt painter",
    "matt painter's",
    "zach edey",
    "mackey arena",
    "west lafayette",
    "braden smith",
    "fletcher loyer",
    "boilers",
    "boilermaker",
]

# We will also include other college hoops headlines for context,
# BUT we boost (score) Purdue-heavy stuff so it floats to top.
EXTRA_KEYWORDS = [
    "big ten",
    "march madness",
    "ncaa tournament",
    "college basketball",
]

# Max number of articles we’ll keep
MAX_ITEMS = 30

USER_AGENT = (
    "Mozilla/5.0 (compatible; PurdueMBBFanFeed/1.0; +https://github.com/jasonab74-ctrl)"
)

# ---------------------------
# HELPERS
# ---------------------------

def load_sources():
    with open(SOURCES_PATH, "r") as f:
        return json.load(f)

def fetch_rss(url: str):
    """
    Try to parse RSS/Atom. Returns list[dict] with minimal keys:
    {title, summary, link, published_ts, source_name}
    We do NOT crash if feed is bad.
    """
    try:
        d = feedparser.parse(url)
        items = []
        for entry in d.entries:
            title = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "").strip()
            link = getattr(entry, "link", "").strip()

            # published / updated
            published_ts = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_ts = int(time.mktime(entry.published_parsed))
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published_ts = int(time.mktime(entry.updated_parsed))

            items.append(
                {
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published_ts": published_ts,
                }
            )
        return items
    except Exception:
        return []

def fetch_html(url: str, selector_rules: dict):
    """
    "Poor man's scrape" for sources that don't expose RSS.
    selector_rules looks like:
    {
      "item": ".story-card",
      "title": ".headline",
      "summary": ".dek",
      "link": "a",
      "time": "time"
    }
    Everything is best-effort / safe-fail.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    except Exception:
        return []

    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select(selector_rules.get("item", "")) or []
    results = []
    for card in cards:
        title_el = card.select_one(selector_rules.get("title", ""))
        summary_el = card.select_one(selector_rules.get("summary", ""))
        link_el = card.select_one(selector_rules.get("link", "a"))
        time_el = card.select_one(selector_rules.get("time", ""))

        title = (title_el.get_text(" ", strip=True) if title_el else "").strip()
        summary = (summary_el.get_text(" ", strip=True) if summary_el else "").strip()
        link = ""
        if link_el and link_el.has_attr("href"):
            link = link_el["href"].strip()
            # make absolute if needed
            if link.startswith("/"):
                parsed = urlparse(url)
                link = f"{parsed.scheme}://{parsed.netloc}{link}"

        published_ts = None
        if time_el:
            # attempt to parse datetime attr first
            dt_val = ""
            if time_el.has_attr("datetime"):
                dt_val = time_el["datetime"]
            else:
                dt_val = time_el.get_text(strip=True)
            published_ts = try_parse_datetime_to_epoch(dt_val)

        # If there's literally no text, skip
        if not title and not summary:
            continue

        results.append(
            {
                "title": title,
                "summary": summary,
                "link": link,
                "published_ts": published_ts,
            }
        )

    return results

def try_parse_datetime_to_epoch(dt_str: str):
    """
    Try a couple common formats → epoch (int).
    If it fails, return None.
    """
    if not dt_str:
        return None

    FORMATS = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]
    for fmt in FORMATS:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return int(dt.timestamp())
        except Exception:
            pass
    return None

def clean_text(t: str) -> str:
    """
    Clean up the '&#39;' junk etc so it doesn't look broken on page.
    """
    if not t:
        return ""
    # Minimal HTML entity cleanup for common cases.
    t = (
        t.replace("&#39;", "'")
        .replace("&apos;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&nbsp;", " ")
    )
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

def score_item(title: str, summary: str, source_name: str) -> float:
    """
    Heuristic scoring:
    - big boost if we see Purdue/Matt Painter/etc
    - medium boost if Big Ten / college basketball
    - tiny boost if source is hyper-relevant (GoldandBlack, On3 Purdue, etc.)
    """
    text = f"{title} {summary}".lower()
    score = 0.0

    # Purdue-heavy?
    for kw in PURDUE_KEYWORDS:
        if kw in text:
            score += 5.0  # strong Purdue signal

    # General college hoops context
    for kw in EXTRA_KEYWORDS:
        if kw in text:
            score += 1.0

    # Prefer Purdue-specific outlets
    if any(x in source_name.lower() for x in [
        "goldandblack",
        "purdue athletics",
        "purdue mbb",
        "boilermakers",
        "on3",
        "247sports",
        "si purdue",
    ]):
        score += 2.0

    return score

def dedupe(items):
    """
    Avoid obvious duplicates (same normalized title).
    """
    seen = set()
    unique = []
    for it in items:
        norm_title = re.sub(r"\W+", "", it["title"].lower())
        if norm_title in seen:
            continue
        seen.add(norm_title)
        unique.append(it)
    return unique

def build_item_id(link: str, title: str) -> str:
    raw = (link or "") + "|" + title
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return h

def epoch_to_iso8601(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

# ---------------------------
# MAIN COLLECT
# ---------------------------

def main():
    print("🔄 Loading sources...")
    sources = load_sources()

    all_items = []

    for src in sources:
        name = src.get("name", "Unknown Source").strip()
        feed_url = src.get("rss")  # may be None
        scrape = src.get("scrape", {})  # {url, selectors{}}

        pulled = []

        if feed_url:
            pulled = fetch_rss(feed_url)
        elif scrape:
            pulled = fetch_html(
                scrape.get("url", ""),
                scrape.get("selectors", {})
            )

        # normalize + annotate
        for p in pulled:
            title = clean_text(p.get("title", ""))
            summary = clean_text(p.get("summary", ""))
            link = p.get("link") or ""
            published_ts = p.get("published_ts") or None

            if not title and not summary:
                continue

            all_items.append(
                {
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "published_ts": published_ts,
                    "source": name,
                }
            )

    print(f"📦 Pulled raw {len(all_items)} items")

    # score
    for it in all_items:
        it["score"] = score_item(it["title"], it["summary"], it["source"])

    # sort by score desc then recency desc
    all_items.sort(
        key=lambda x: (
            x["score"],
            x["published_ts"] if x["published_ts"] else 0
        ),
        reverse=True,
    )

    # dedupe on title-ish
    all_items = dedupe(all_items)

    # slice
    final_items = all_items[:MAX_ITEMS]

    # final shape for site
    now_iso = datetime.now(timezone.utc).isoformat()
    site_items = []
    for it in final_items:
        site_items.append(
            {
                "id": build_item_id(it["url"], it["title"]),
                "source": it["source"],
                "title": it["title"],
                "summary": it["summary"],
                "url": it["url"],
                "published": epoch_to_iso8601(it["published_ts"]),
            }
        )

    output_obj = {
        "updated": now_iso,
        "items": site_items,
    }

    # write
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output_obj, f, indent=2)

    print(f"✅ Wrote {len(site_items)} stories to {OUTPUT_PATH}")
    print("Done.")

if __name__ == "__main__":
    main()