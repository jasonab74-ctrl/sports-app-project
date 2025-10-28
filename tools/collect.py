#!/usr/bin/env python3
#
# collect.py
#
# Pulls recent Purdue men's basketball news from multiple sources,
# filters / scores it, dedupes it, sorts newest -> oldest,
# and writes it to static/teams/purdue-mbb/items.json for the site.

import os
import json
import time
import hashlib
import feedparser
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

###############################################################################
# 1. CONFIG: SOURCES
###############################################################################

SOURCES = [
    # Purdue official athletics feed (MBB path, but includes other Purdue sports content)
    {
        "name": "Purdue Athletics MBB",
        "url": "https://purduesports.com/rss?path=mbball",
        "type": "rss",
        "trusted": True,
    },
    # GoldandBlack / On3 / etc. – if these feeds don't work publicly we’ll still try;
    # if they fail, we just won't add anything from them. That’s fine.
    {
        "name": "GoldandBlack.com",
        "url": "https://www.on3.com/teams/purdue-boilermakers/feed/",  # (placeholder if scraped later)
        "type": "html-list",
        "trusted": True,
    },
    {
        "name": "Yahoo Sports College Basketball",
        "url": "https://sports.yahoo.com/college-basketball/rss/",
        "type": "rss",
        "trusted": False,
    },
    {
        "name": "CBS Sports College Basketball",
        "url": "https://www.cbssports.com/college-basketball/rss/headlines/",
        "type": "rss",
        "trusted": False,
    },
    {
        "name": "USA Today Purdue Boilermakers",
        "url": "https://usatoday.com/sports/college/purdue/rss",  # placeholder/guess
        "type": "rss",
        "trusted": False,
    },
    {
        "name": "The Field of 68",
        "url": "https://thefieldof68.com/feed",  # wordpress style
        "type": "rss",
        "trusted": False,
    },
    {
        "name": "SI Purdue Basketball",
        "url": "https://www.si.com/rss/college/purdue",  # placeholder
        "type": "rss",
        "trusted": False,
    },
    {
        "name": "247Sports Purdue Basketball",
        "url": "https://247sports.com/college/purdue/Content/Feed.rss",  # placeholder
        "type": "rss",
        "trusted": False,
    },
    {
        "name": "ESPN Purdue MBB",
        "url": "https://www.espn.com/college-basketball/team/_/id/2509/purdue-boilermakers",  # HTML scrape later
        "type": "html-list",
        "trusted": True,
    },
]

###############################################################################
# 2. KEYWORDS & FILTERING
###############################################################################

# Words/phrases that STRONGLY indicate Purdue men's basketball
BASKETBALL_POSITIVE_TERMS = [
    "purdue basketball",
    "boilermakers basketball",
    "purdue men's basketball",
    "purdue men's hoops",
    "purdue mbb",
    "matt painter",
    "braden smith",
    "fletcher loyer",
    "trey kaufman-renn",
    "zach edey",
    "boilermakers go perfect",
    "exhibition win",
    "kentucky in exhibition",
    "purdue vs kentucky",
    "media session | purdue men's basketball",
    "press conference | purdue men's basketball",
    "preseason all-america",
    "wake forest",
    "home exhibition tuneup",
    "day of 2 rome invite",  # golfing/other sports may still sneak in, so we won't rely ONLY on positives
]

# Sports/topics we want to EXCLUDE if it's *not* clearly men's hoops
NEGATIVE_NON_BASKETBALL_TERMS = [
    "purdue football",
    "football",
    "press conference | purdue football",
    "postgame press conference | purdue football",
    "wr ",
    "db ",
    "oc ",
    "dc ",
    "te ",
    "purdue volleyball",
    "volleyball",
    "purdue soccer",
    "soccer",
    "wrestling",
    "wrestling season preview",
    "purdue baseball",
    "baseball",
    "halloween bash at alexander field",
    "purdue's annual free and all ages halloween bash",
]

# If a headline looks like men's hoops (Painter, vs Kentucky, etc.) we keep it
# even if football words accidentally appear.
# If it does NOT look like hoops, and it DOES look like football/volleyball/baseball/etc,
# we drop it.


###############################################################################
# 3. HELPERS
###############################################################################

def safe_get(entry, keys, default=None):
    """Try a list of keys on an object that might be dict-like or attr-like."""
    for k in keys:
        if isinstance(entry, dict) and k in entry:
            return entry[k]
        if hasattr(entry, k):
            return getattr(entry, k)
    return default


def clean_html_entities(text):
    """Turn &#39; etc. into straight quotes, etc."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(" ", strip=True)
    return (
        cleaned
        .replace("&#39;", "'")
        .replace("&apos;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&#34;", '"')
        .replace("&#38;", "&")
        .replace("&#x27;", "'")
    )


def parse_datetime_struct(struct_time_val):
    """
    Given a time.struct_time (what feedparser gives in .published_parsed),
    return epoch seconds.
    If missing/None/bad -> return None.
    """
    try:
        if struct_time_val is None:
            return None
        return int(time.mktime(struct_time_val))
    except Exception:
        return None


def iso_from_epoch(epoch_secs):
    """Return ISO8601 string in UTC for storage, e.g. '2025-10-28T14:05:00Z'."""
    if epoch_secs is None:
        return None
    return datetime.fromtimestamp(epoch_secs, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short_date_from_epoch(epoch_secs):
    """Return short 'Oct 27' style for display."""
    if epoch_secs is None:
        return ""
    dt = datetime.fromtimestamp(epoch_secs, tz=timezone.utc)
    return dt.strftime("%b %d")


def score_item(title, summary, source_name):
    """
    Heuristic "is this Purdue MBB?" score.

    Strategy:
    - Base score 0
    - +2 if source is a trusted Purdue source (official MBB, etc.)
    - +2 if "purdue" and "basketball" both appear in title or summary
    - +2 if any known Purdue MBB player / coach / exact hoops term shows up
    - -2 if clearly football/volleyball/baseball/etc AND not clearly hoops

    We don't need perfect AI. We just need "good enough to push hoops to top".
    """
    text = f"{title} {summary}".lower()

    score = 0

    # trusted sources bump
    # (your "trusted": True in SOURCES means we lean toward including it,
    #  as long as it isn't obviously football/baseball/etc)
    is_trusted = False
    for src in SOURCES:
        if src["name"] == source_name and src.get("trusted"):
            is_trusted = True
            break
    if is_trusted:
        score += 2

    # Purdue + basketball as a pair?
    if "purdue" in text and "basketball" in text:
        score += 2

    # Positive hoops markers
    for kw in BASKETBALL_POSITIVE_TERMS:
        if kw.lower() in text:
            score += 2
            break

    # Negative markers (football/baseball/etc.)
    found_negative = any(bad.lower() in text for bad in NEGATIVE_NON_BASKETBALL_TERMS)

    # If it's clearly negative AND we didn't already get strong hoops signals,
    # knock it down.
    # We'll interpret "strong hoops signals" as: score < 2 means "not strong yet".
    if found_negative and score < 2:
        score -= 2

    return score


def looks_like_duplicate(a, b):
    """
    Quick duplicate check. If headlines are ~the same after cleaning,
    treat them as dupes so we don't show 2 copies.
    """
    ta = clean_html_entities(a).strip().lower()
    tb = clean_html_entities(b).strip().lower()
    return ta == tb


def fetch_rss(source):
    """Return list[dict] of normalized items from an RSS/Atom feed."""
    out = []
    try:
        parsed = feedparser.parse(source["url"])
    except Exception:
        return out

    for entry in parsed.entries:
        raw_title = safe_get(entry, ["title"], "")
        raw_summary = safe_get(entry, ["summary", "description"], "")
        link = safe_get(entry, ["link"], "")
        published_epoch = parse_datetime_struct(
            safe_get(entry, ["published_parsed", "updated_parsed"], None)
        )

        title = clean_html_entities(raw_title)
        summary = clean_html_entities(raw_summary)

        out.append({
            "source": source["name"],
            "title": title,
            "summary": summary,
            "url": link,
            "published_epoch": published_epoch,
        })
    return out


def fetch_html_list(source):
    """
    Placeholder for HTML sources that don't have clean RSS.
    We'll try a very light scrape. If it fails, just return [].
    We'll keep it very forgiving so we don't crash the run.
    """
    out = []
    try:
        resp = requests.get(source["url"], timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return out
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extremely light heuristic:
        # grab <a> headlines in something that looks like article blocks.
        # We'll just pull top ~10 anchors that look newsy.
        anchors = soup.find_all("a", limit=20)
        for a in anchors:
            headline = a.get_text(" ", strip=True)
            if not headline or len(headline) < 20:
                continue
            href = a.get("href") or ""
            # build absolute URL if needed
            if href.startswith("/"):
                # naive absolute:
                base = source["url"].rstrip("/")
                href = base + href

            # fake summary for now
            summary = ""
            published_epoch = None  # we usually don't get time here w/out deeper scrape

            out.append({
                "source": source["name"],
                "title": clean_html_entities(headline),
                "summary": clean_html_entities(summary),
                "url": href,
                "published_epoch": published_epoch,
            })
    except Exception:
        return []
    return out


###############################################################################
# 4. MAIN COLLECT LOGIC
###############################################################################

def collect_all():
    raw_items = []

    for src in SOURCES:
        if src["type"] == "rss":
            items = fetch_rss(src)
        elif src["type"] == "html-list":
            items = fetch_html_list(src)
        else:
            items = []

        raw_items.extend(items)

    # Score / filter
    scored_items = []
    for it in raw_items:
        s = score_item(it["title"], it["summary"], it["source"])

        # Keep anything that scores >= 1
        # This usually means "likely Purdue hoops"
        # PLUS: if it's trusted source with no timestamp (like scraped),
        # we still might keep it, but only if it didn't get hammered negative.
        if s >= 1:
            scored_items.append({
                **it,
                "score": s,
            })

    # Dedupe by title
    deduped = []
    for item in scored_items:
        if any(looks_like_duplicate(item["title"], d["title"]) for d in deduped):
            continue
        deduped.append(item)

    # Sort newest -> oldest:
    # Rule:
    #   first: published_epoch DESC (None should go last)
    #   tie-breaker: score DESC
    def sort_key(x):
        # if no published_epoch, treat as 0 so they fall to the bottom
        pe = x["published_epoch"] if x["published_epoch"] is not None else 0
        return (pe, x["score"])

    deduped.sort(key=sort_key, reverse=True)

    # Final normalize for site JSON
    final_items = []
    for it in deduped:
        final_items.append({
            "source": it["source"],
            "headline": it["title"],
            "summary": it["summary"],
            "url": it["url"],
            "published": short_date_from_epoch(it["published_epoch"]),
            "published_iso": iso_from_epoch(it["published_epoch"]),
        })

    return final_items


###############################################################################
# 5. WRITE TO DISK
###############################################################################

def main():
    data = collect_all()

    # Ensure output dir exists
    out_path = os.path.join("static", "teams", "purdue-mbb")
    os.makedirs(out_path, exist_ok=True)

    out_file = os.path.join(out_path, "items.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(data)} items to {out_file}")


if __name__ == "__main__":
    main()