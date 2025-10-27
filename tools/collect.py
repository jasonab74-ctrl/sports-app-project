#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball collector.

Changes in this version:
- Uses scoring logic instead of simple yes/no filters.
- Tries hard to include only Purdue MBB content.
- Penalizes football/baseball/etc. so they don't leak in.
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
        "published": ISO8601 string,
        "snippet": ...,
        "image": "",
        "collected_at": ""   (filled later)
    }
    """
    out = []
    if not xml_bytes:
        return out

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    # Try RSS 2.0 structure: <rss><channel><item>...</item></channel></rss>
    channel = root.find("channel")
    if channel is not None:
        item_nodes = channel.findall("item")
    else:
        # Try Atom structure: <feed><entry>...</entry></feed>
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
            # Atom feeds use <link href="...">
            link_el = node.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.attrib.get("href", "").strip()

        # description/snippet
        desc = (
            node.findtext("description")
            or node.findtext("{http://www.w3.org/2005/Atom}summary")
            or ""
        ).strip()

        # pubDate / updated / published
        pub_raw = (
            node.findtext("pubDate")
            or node.findtext("{http://www.w3.org/2005/Atom}updated")
            or node.findtext("{http://www.w3.org/2005/Atom}published")
            or ""
        ).strip()

        # convert pub_raw into ISO8601
        published_iso = None
        if pub_raw:
            try:
                dt = email.utils.parsedate_to_datetime(pub_raw)
                published_iso = dt.isoformat(timespec="seconds") + "Z"
            except Exception:
                published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        else:
            published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        # normalize snippet to ~240 chars, single line
        snippet_clean = desc.replace("\n", " ").strip()
        if len(snippet_clean) > 240:
            snippet_clean = snippet_clean[:237].rstrip() + "…"

        out.append({
            "source": source_name,
            "title": title,
            "url": link,
            "published": published_iso,
            "snippet": snippet_clean,
            "image": "",
            "collected_at": ""  # we'll stamp in save step
        })

    return out


# -------- Purdue MBB relevance scoring --------
def score_story(story):
    """
    Give the story a numeric score. Higher = more likely to be Purdue men's basketball.

    We'll look at:
    - Purdue signals
    - Men's hoops signals
    - Trusted source signals
    - Non-basketball sports signals (which we subtract)

    At the end we'll return a score like 0, 3, 7, etc.
    We'll keep only stories above a threshold.
    """
    title = story.get("title", "").lower()
    snippet = story.get("snippet", "").lower()
    src = story.get("source", "").lower()

    blob = f"{title} {snippet}"

    score = 0

    # Strong Purdue ID signals
    purdue_hits = [
        "purdue",
        "boilermaker",
        "boilermakers",
        "boilers",
        "mackey",
        "west lafayette",
        "matt painter",
        "painter",
    ]
    if any(k in blob for k in purdue_hits):
        score += 3

    # Men's basketball specific language
    hoops_hits = [
        "basketball",
        "mbb",
        "men's basketball",
        "mens basketball",
        "backcourt",
        "back court",
        "frontcourt",
        "front court",
        "guard play",
        "point guard",
        "ball screen",
        "wingspan",
        "3-point",
        "three-point",
        "perimeter",
        "pick-and-roll",
        "pick and roll",
        "big ten",
        "ncaa tournament",
        "march madness",
        "big man",
        "rim protector",
        "painter said",    # often shows up in quotes
        "painter says",
    ]
    if any(k in blob for k in hoops_hits):
        score += 3

    # Recruiting that looks like hoops (PG, SG, wing, combo guard, 4-star guard, etc.)
    recruit_hits = [
        "commit",
        "commits",
        "commitment",
        "signed",
        "signs",
        "4-star",
        "five-star",
        "five star",
        "4 star",
        "point guard",
        "shooting guard",
        "combo guard",
        "wing",
        "stretch four",
        "6-foot-",
        "6’",
        "6′",
        "offer from purdue",
        "purdue offer",
    ]
    # Light bump, because recruiting is relevant content
    if any(k in blob for k in recruit_hits):
        score += 1

    # Trusted sources get bonus because they mostly talk hoops already
    trusted_sources = [
        "goldandblack",
        "on3",
        "purdue athletics",
        "espn",
        "field of 68",
        "field of68",
        "fieldof68",
    ]
    if any(t in src for t in trusted_sources):
        score += 2

    # Now subtract if it's clearly another sport.
    # We detect and subtract hard here to kill false positives like
    # "Purdue lands 3-star WR" or "Purdue vs. Iowa football".
    non_basketball_hits = [
        "football",
        "qb",
        "quarterback",
        "offensive line",
        "o-line",
        "o line",
        "defensive line",
        "d-line",
        "d line",
        "linebacker",
        "wide receiver",
        "receiver",
        "wr",
        "running back",
        "tailback",
        "rb",
        "touchdown",
        "td run",
        "field goal",
        "touchback",
        "kickoff",
        "kick return",
        "baseball",
        "softball",
        "volleyball",
        "soccer",
        "wrestling",
        "track and field",
        "golf",
    ]
    if any(k in blob for k in non_basketball_hits):
        score -= 5

    return score


def keep_purdue_mbb(stories, min_score=4):
    """
    Keep only stories with score >= min_score.
    Default threshold is 4:
    - That usually means: either Purdue+hoops, or Purdue+trusted source,
      and not obviously football.
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
    - Fetch all RSS feeds from sources.json
    - Parse stories from each
    - Score & filter stories for Purdue MBB
    - Sort newest first by published timestamp
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

    # Filter by score
    filtered = keep_purdue_mbb(all_items, min_score=4)

    # Sort newest first by 'published'
    def sort_key(item):
        return item.get("published", "")
    filtered.sort(key=sort_key, reverse=True)

    # Keep top 20
    filtered = filtered[:20]

    # Stamp collected_at for every item
    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for it in filtered:
        it["collected_at"] = now_iso

    return filtered


# -------- Save items.json --------
def save_items(items):
    """
    Write JSON back to static/teams/purdue-mbb/items.json in the shape:
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
    If we get nothing (network down, feeds changed, etc.), don't blank the page:
    - reuse existing items.json, just refresh collected_at
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
            # nothing to fall back to, just save empty list
            save_items([])
        return

    # We got fresh stories
    save_items(stories)


if __name__ == "__main__":
    main()