#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball collector — tuned version.

Upgrades in this version:
- Keeps score-based filtering (smart relevance detection)
- Adds +3 bias for trusted Purdue sources (GoldandBlack, On3, 247, Purdue Athletics)
- Keeps national CBB feeds but downweights them unless they mention Purdue directly
- Keeps min_score=2 for decent recall
- Produces top 20 sorted by score then recency
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
    """Extract basic fields from RSS/Atom feeds."""
    out = []
    if not xml_bytes:
        return out

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    channel = root.find("channel")
    if channel is not None:
        item_nodes = channel.findall("item")
    else:
        item_nodes = root.findall("{http://www.w3.org/2005/Atom}entry")

    for node in item_nodes:
        title = (
            node.findtext("title")
            or node.findtext("{http://www.w3.org/2005/Atom}title")
            or ""
        ).strip()

        link = node.findtext("link") or ""
        if not link:
            link_el = node.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.attrib.get("href", "").strip()

        desc = (
            node.findtext("description")
            or node.findtext("{http://www.w3.org/2005/Atom}summary")
            or node.findtext("{http://www.w3.org/2005/Atom}content")
            or ""
        ).strip()

        pub_raw = (
            node.findtext("pubDate")
            or node.findtext("{http://www.w3.org/2005/Atom}updated")
            or node.findtext("{http://www.w3.org/2005/Atom}published")
            or ""
        ).strip()

        # Convert to ISO8601
        if pub_raw:
            try:
                dt = email.utils.parsedate_to_datetime(pub_raw)
                published_iso = dt.isoformat(timespec="seconds") + "Z"
            except Exception:
                published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        else:
            published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        snippet = desc.replace("\n", " ").replace("\r", " ").strip()
        if len(snippet) > 240:
            snippet = snippet[:237].rstrip() + "…"

        out.append({
            "source": source_name,
            "title": title,
            "url": link,
            "published": published_iso,
            "snippet": snippet,
            "image": "",
            "collected_at": ""
        })
    return out


# -------- Scoring logic --------
def score_story(story):
    """Assigns a weighted score indicating Purdue MBB relevance."""
    title = story.get("title", "").lower()
    snippet = story.get("snippet", "").lower()
    src = story.get("source", "").lower()
    blob = f"{title} {snippet}"

    score = 0

    # Strong Purdue context
    purdue_terms = [
        "purdue", "boilermaker", "boilermakers", "boilers",
        "mackey", "west lafayette", "painter", "matt painter"
    ]
    if any(k in blob for k in purdue_terms):
        score += 3

    # Basketball context
    hoops_terms = [
        "basketball", "mbb", "men's basketball", "mens basketball", "men’s basketball",
        "ncaa tournament", "march madness", "big ten",
        "backcourt", "frontcourt", "guard play", "point guard", "ball screen",
        "pick-and-roll", "pick and roll", "perimeter", "3-point", "three-point",
        "rim protector", "stretch four", "paint touches", "rotation", "starting lineup"
    ]
    if any(k in blob for k in hoops_terms):
        score += 3

    # Recruiting terms (light bonus)
    recruit_terms = [
        "commit", "commits", "commitment", "signed", "signs",
        "offer from purdue", "purdue offer", "4-star", "five-star", "five star", "4 star",
        "point guard", "shooting guard", "combo guard", "wing", "6-foot-", "6’", "6′"
    ]
    if any(k in blob for k in recruit_terms):
        score += 1

    # Non-basketball penalties
    other_sports = [
        "football", "quarterback", "qb", "wide receiver", "running back",
        "tailback", "field goal", "touchdown", "kickoff", "linebacker", "defensive line",
        "baseball", "softball", "volleyball", "soccer", "wrestling", "track", "golf"
    ]
    if any(k in blob for k in other_sports):
        score -= 5

    # Trusted source weighting
    trusted_purdue_sources = [
        "goldandblack", "on3", "247sports", "purdue athletics", "si", "sports illustrated"
    ]
    if any(t in src for t in trusted_purdue_sources):
        score += 3  # strong priority

    # National but basketball-related sources (mild bump)
    national_cbb = ["espn", "cbs sports", "field of 68", "yahoo sports", "usa today"]
    if any(n in src for n in national_cbb):
        score += 1

    return score


def keep_purdue_mbb(stories, min_score=2):
    """Return only Purdue MBB stories with score >= threshold."""
    kept = []
    for s in stories:
        sc = score_story(s)
        if sc >= min_score:
            s["score"] = sc
            kept.append(s)
    return kept


# -------- Load sources --------
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
    """Fetch, parse, filter, sort, and prepare items."""
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

    filtered = keep_purdue_mbb(all_items, min_score=2)

    # Sort by score first, then by published date
    def sort_key(item):
        return (item.get("score", 0), item.get("published", ""))
    filtered.sort(key=sort_key, reverse=True)

    filtered = filtered[:20]
    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for it in filtered:
        it["collected_at"] = now_iso

    return filtered


# -------- Save to items.json --------
def save_items(items):
    """Write items JSON for the site."""
    ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {"items": items}
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


# -------- Main --------
def main():
    stories = collect_all()
    if not stories:
        print("No new stories found — falling back to existing items.json")
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