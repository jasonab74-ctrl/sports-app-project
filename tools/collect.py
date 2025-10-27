#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball collector.

What this script does:
- Loads RSS/Atom feeds from static/sources.json
- Fetches them (urllib only, stdlib only)
- Parses each item (title, link, description, published date)
- Scores each story for "Is this Purdue men's basketball?"
- Keeps only good ones
- Sorts, trims to top 20
- Writes static/teams/purdue-mbb/items.json for the site

This pairs with:
- .github/workflows/collect.yml  (hourly job)
- static/js/pro.js               (renders cards)
"""

import json
import datetime
import email.utils
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# -------- Paths --------
ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "static" / "sources.json"
ITEMS_PATH = ROOT / "static" / "teams" / "purdue-mbb" / "items.json"


# -------- HTTP fetch --------
def http_get(url, timeout=10):
    """Fetch bytes from a URL using stdlib only."""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (URLError, HTTPError) as e:
        print("fetch fail", url, e)
        return b""


# -------- RSS parsing --------
def parse_rss(xml_bytes, source_name):
    """
    Given raw RSS/Atom bytes, return a list of story dicts:
    {
        "source": source_name,
        "title": ...,
        "url": ...,
        "published": ISO8601,
        "snippet": ...,
        "image": "",
        "collected_at": ""  (we'll stamp later)
    }
    """
    out = []
    if not xml_bytes:
        return out

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    # Try RSS 2.0 style: <rss><channel><item>...</item></channel></rss>
    channel = root.find("channel")
    if channel is not None:
        item_nodes = channel.findall("item")
    else:
        # Try Atom style: <feed><entry>...</entry></feed>
        item_nodes = root.findall("{http://www.w3.org/2005/Atom}entry")

    for node in item_nodes:
        # title
        title = (
            node.findtext("title")
            or node.findtext("{http://www.w3.org/2005/Atom}title")
            or ""
        ).strip()

        # link
        link = node.findtext("link") or ""
        if not link:
            # Atom feeds commonly do <link href="..."/>
            link_el = node.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.attrib.get("href", "").strip()

        # description/snippet
        desc = (
            node.findtext("description")
            or node.findtext("{http://www.w3.org/2005/Atom}summary")
            or node.findtext("{http://www.w3.org/2005/Atom}content")
            or ""
        ).strip()

        # publish date-ish
        pub_raw = (
            node.findtext("pubDate")
            or node.findtext("{http://www.w3.org/2005/Atom}updated")
            or node.findtext("{http://www.w3.org/2005/Atom}published")
            or ""
        ).strip()

        # convert pub_raw into ISO8601
        if pub_raw:
            try:
                dt = email.utils.parsedate_to_datetime(pub_raw)
                published_iso = dt.isoformat(timespec="seconds") + "Z"
            except Exception:
                published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        else:
            published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        # clean snippet down to ~240 chars
        snippet_clean = desc.replace("\n", " ").replace("\r", " ").strip()
        if len(snippet_clean) > 240:
            snippet_clean = snippet_clean[:237].rstrip() + "…"

        out.append({
            "source": source_name,
            "title": title,
            "url": link,
            "published": published_iso,
            "snippet": snippet_clean,
            "image": "",
            "collected_at": ""  # set later
        })

    return out


# -------- Purdue MBB relevance scoring --------
def score_story(story):
    """
    Score how likely this story is Purdue men's basketball.
    Bigger score = more likely we want it.

    We'll add:
      + Purdue signals
      + Men's hoops signals
      + Trusted source signals
      + Recruiting-but-basketball signals

    We'll subtract:
      - Football/baseball/other sport terms
    """
    title = story.get("title", "").lower()
    snippet = story.get("snippet", "").lower()
    src = story.get("source", "").lower()
    blob = f"{title} {snippet}"

    score = 0

    # Strong Purdue ID / program context
    purdue_hits = [
        "purdue",
        "boilermaker",
        "boilermakers",
        "boilers",
        "mackey",
        "west lafayette",
        "matt painter",
        "painter"
    ]
    if any(k in blob for k in purdue_hits):
        score += 3

    # Men's basketball language
    hoops_hits = [
        "basketball",
        "mbb",
        "men's basketball",
        "mens basketball",
        "men’s basketball",
        "ncaa tournament",
        "march madness",
        "big ten",
        "backcourt",
        "frontcourt",
        "guard play",
        "point guard",
        "ball screen",
        "pick-and-roll",
        "pick and roll",
        "perimeter",
        "3-point",
        "three-point",
        "rim protector",
        "stretch four",
        "paint touches",
        "rebound",
        "wing depth",
        "rotation",
        "starting five",
        "starting lineup"
    ]
    if any(k in blob for k in hoops_hits):
        score += 3

    # Recruiting context that smells like hoops
    recruit_hits = [
        "commit",
        "commits",
        "commitment",
        "signs",
        "signed",
        "offer from purdue",
        "purdue offer",
        "4-star",
        "five-star",
        "five star",
        "4 star",
        "point guard",
        "shooting guard",
        "combo guard",
        "wing",
        "6-foot-",
        "6’",
        "6′"
    ]
    if any(k in blob for k in recruit_hits):
        score += 1

    # Trusted basketball-ish sources get a bump
    trusted_sources = [
        "goldandblack",
        "on3",
        "purdue athletics",
        "espn",
        "cbs sports",
        "field of 68",
        "field of68",
        "fieldof68"
    ]
    if any(t in src for t in trusted_sources):
        score += 2

    # Subtract obvious non-basketball sports refs
    # This kills "Purdue lands 3-star WR" etc.
    non_basketball_hits = [
        "football",
        "qb",
        "quarterback",
        "wide receiver",
        "receiver",
        "wr ",
        " wr",
        "running back",
        "tailback",
        "rb ",
        " rb",
        "touchdown",
        "field goal",
        "kickoff",
        "o-line",
        "o line",
        "offensive line",
        "d-line",
        "d line",
        "defensive line",
        "linebacker",
        "sack",
        "interception",
        "baseball",
        "softball",
        "volleyball",
        "soccer",
        "wrestling",
        "track and field",
        "golf"
    ]
    if any(k in blob for k in non_basketball_hits):
        score -= 5

    return score


def keep_purdue_mbb(stories, min_score=2):
    """
    Keep only stories with score >= min_score.
    We are using min_score=2 to be a bit more generous so that
    we fill the page with legit Purdue hoops talk.
    """
    kept = []
    for s in stories:
        sc = score_story(s)
        if sc >= min_score:
            kept.append(s)
    return kept


# -------- Load list of sources --------
def load_sources():
    try:
        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("sources", [])
    except Exception as e:
        print("failed to read sources.json", e)
        return []


# -------- Collect all feeds --------
def collect_all():
    """
    - Pull all feeds from sources.json
    - Parse items
    - Filter/score for Purdue MBB
    - Sort newest first
    - Trim to top 20
    - Stamp collected_at
    """
    sources = load_sources()
    all_items = []

    for src in sources:
        if src.get("type") != "rss":
            continue
        url = src.get("url")
        if not url:
            continue

        raw = http_get(url)
        parsed = parse_rss(raw, src.get("name", ""))
        all_items.extend(parsed)

    # Score + filter
    filtered = keep_purdue_mbb(all_items, min_score=2)

    # Sort newest first
    def sort_key(item):
        return item.get("published", "")
    filtered.sort(key=sort_key, reverse=True)

    # Cap at 20
    filtered = filtered[:20]

    # Stamp collected_at for UI badge
    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for it in filtered:
        it["collected_at"] = now_iso

    return filtered


# -------- Save items.json --------
def save_items(items):
    """
    Write JSON back to static/teams/purdue-mbb/items.json
    Shape:
    {
      "items": [...]
    }
    """
    ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {"items": items}
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


# -------- Main entry --------
def main():
    """
    Try to pull fresh data.
    If we somehow get nothing, reuse whatever's already in items.json
    so the live site never goes blank.
    """
    stories = collect_all()

    if not stories:
        print("No new stories found. Falling back to existing items.json")
        try:
            current_raw = ITEMS_PATH.read_text("utf-8")
            current_json = json.loads(current_raw)
            existing_items = current_json.get("items", [])
        except Exception:
            existing_items = []

        if existing_items:
            now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            for it in existing_items:
                it["collected_at"] = now_iso
            save_items(existing_items)
        else:
            save_items([])
        return

    save_items(stories)


if __name__ == "__main__":
    main()