#!/usr/bin/env python3
"""
tools/collect.py

Minimal Purdue MBB collector.

What this script does:
- Reads RSS feeds from static/sources.json
- Downloads each feed (urllib only / stdlib only)
- Parses items out of the RSS/Atom
- Filters to Purdue men's basketball content
- Sorts newest first
- Keeps top 20
- Stamps collected_at (used for "Updated HH:MM AM/PM" in the UI)
- Writes to static/teams/purdue-mbb/items.json

This is designed to run in GitHub Actions (collect-purdue-mbb workflow).
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
        "collected_at": ""   (we'll stamp later)
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


# -------- Filtering to Purdue men's basketball --------
def keep_purdue_mbb(stories):
    """
    Story makes the cut if:
    - It clearly references Purdue / Boilermakers / Painter / Boilers / Mackey, etc.
    AND
    - (It looks hoops-ish: basketball / guard play / backcourt / Big Ten talk / etc.)
      OR
    - It comes from a known Purdue basketball source (GoldandBlack, On3 Purdue, Purdue Athletics MBB, ESPN Purdue MBB)

    This is intentionally a *little* more forgiving than the first draft so
    we actually surface more than 1 headline.
    """
    filtered = []

    for s in stories:
        title = s.get("title", "").lower()
        snippet = s.get("snippet", "").lower()
        src = s.get("source", "").lower()

        text_blob = f"{title} {snippet}"

        is_purdue = (
            "purdue" in text_blob or
            "boilermaker" in text_blob or
            "boilermakers" in text_blob or
            "boilers" in text_blob or
            "painter" in text_blob or
            "mackey" in text_blob
        )

        is_hoops = (
            "basketball" in text_blob or
            "mbb" in text_blob or
            "men's" in text_blob or
            "mens" in text_blob or
            "guard" in text_blob or
            "backcourt" in text_blob or
            "big ten" in text_blob or
            "paint" in text_blob or  # paint touches / post play often shows up in Purdue coverage
            "3-point" in text_blob or
            "three-point" in text_blob or
            "perimeter" in text_blob or
            "frontcourt" in text_blob or
            "rebound" in text_blob or
            "matt painter" in text_blob
        )

        is_trusted_source = (
            "goldandblack" in src or
            "on3" in src or
            "purdue athletics" in src or
            "espn" in src
        )

        if is_purdue and (is_hoops or is_trusted_source):
            filtered.append(s)

    return filtered


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
    - Filter to Purdue MBB
    - Sort newest first (by published)
    - Trim to top 20
    - Stamp collected