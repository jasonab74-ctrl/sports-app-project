#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball collector (tight Purdue filter).

Goals in this version:
- Keep anything from true Purdue sources (GoldandBlack, On3 Purdue, 247 Purdue,
  Purdue Athletics MBB, SI Purdue). Those are always relevant.
- From national sources (Yahoo Sports, CBS Sports, ESPN, etc.), ONLY keep
  stories that actually mention Purdue / Painter / Boilermakers / etc.
- Score & sort so Purdue-heavy beats generic CBB.
- Write top 20 into static/teams/purdue-mbb/items.json.
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


# -------- Fetch helper --------
def http_get(url, timeout=10):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (URLError, HTTPError) as e:
        print("fetch fail", url, e)
        return b""


# -------- RSS/Atom parsing --------
def parse_rss(xml_bytes, source_name):
    """
    Parse an RSS/Atom feed into normalized dicts:
    {
      "source": source_name,
      "title": ...,
      "url": ...,
      "published": ISO8601,
      "snippet": ...,
      "image": "",
      "collected_at": ""
    }
    """
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
        # title
        title = (
            node.findtext("title")
            or node.findtext("{http://www.w3.org/2005/Atom}title")
            or ""
        ).strip()

        # link
        link = node.findtext("link") or ""
        if not link:
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

        # pub date -> ISO8601
        raw_pub = (
            node.findtext("pubDate")
            or node.findtext("{http://www.w3.org/2005/Atom}updated")
            or node.findtext("{http://www.w3.org/2005/Atom}published")
            or ""
        ).strip()

        if raw_pub:
            try:
                dt = email.utils.parsedate_to_datetime(raw_pub)
                published_iso = dt.isoformat(timespec="seconds") + "Z"
            except Exception:
                published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        else:
            published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

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
            "collected_at": ""
        })

    return out


# -------- Purdue relevance logic --------

def is_trusted_purdue_source(src: str) -> bool:
    """
    These sources are basically always Purdue-focused or directly relevant.
    We trust them even if the article text doesn't explicitly repeat 'Purdue'.
    """
    if not src:
        return False
    s = src.lower()
    trusted_list = [
        "goldandblack",
        "on3",
        "247sports",
        "purdue athletics",
        "si purdue",
        "sports illustrated",
        "usa today purdue",
        "usa today boilermakers",
    ]
    return any(key in s for key in trusted_list)


def mentions_purdue_text(title: str, snippet: str) -> bool:
    """
    Look for Purdue-specific cues in title/snippet.
    We use this to allow / block national feed items.
    """
    blob = f"{title} {snippet}".lower()

    purdue_terms = [
        "purdue",
        "boilermaker",
        "boilermakers",
        "boilers",
        "matt painter",
        "painter",
        "braden smith",
        "fletcher loyer",
        "zach edey",      # historic but still talked about
        "mackey",
        "west lafayette",
        "big ten favorite",
        "big ten favorites",
        "big ten title",
        "no. 1 purdue",
        "number 1 purdue",
        "top-ranked purdue",
        "top ranked purdue"
    ]

    hoops_terms = [
        "basketball",
        "men's basketball",
        "mens basketball",
        "men’s basketball",
        "mbb",
        "guard play",
        "point guard",
        "backcourt",
        "frontcourt",
        "3-point",
        "three-point",
        "rotation",
        "starting lineup",
        "ncaa tournament",
        "march madness",
        "final four"
    ]

    # Must have at least one Purdue term
    if not any(k in blob for k in purdue_terms):
        return False

    # Bonus: if it ALSO has basketball-ish language, we're extra sure
    # but we don't force that second condition because sometimes headlines
    # are just "Purdue, Matt Painter on ...".
    return True


def score_story(story):
    """
    Give a score so we can sort best stuff first.
    We'll boost:
    - trusted Purdue sources
    - explicit Purdue mentions
    - basketball language
    We'll penalize obvious non-basketball sports.
    """
    title = story.get("title", "").lower()
    snippet = story.get("snippet", "").lower()
    src = story.get("source", "").lower()
    blob = f"{title} {snippet}"

    score = 0

    # Trusted insider sources get a high base
    if is_trusted_purdue_source(src):
        score += 10

    # Purdue mentions
    if mentions_purdue_text(title, snippet):
        score += 5

    # Basketball language
    hoops_terms = [
        "basketball", "mbb", "men's basketball", "mens basketball", "men’s basketball",
        "ncaa tournament", "march madness", "big ten",
        "guard play", "point guard", "backcourt", "frontcourt",
        "pick-and-roll", "pick and roll", "3-point", "three-point",
        "rotation", "starting lineup", "rim protector"
    ]
    if any(k in blob for k in hoops_terms):
        score += 2

    # Non-basketball sports penalty
    other_sports = [
        "football", "quarterback", "qb", "wide receiver", "running back",
        "touchdown", "field goal", "kickoff",
        "baseball", "softball", "volleyball", "soccer", "wrestling",
        "track and field", "golf"
    ]
    if any(k in blob for k in other_sports):
        score -= 5

    return score


def should_keep_story(story):
    """
    Decide if a story should even be in the feed.

    Rules:
    - If it's from a trusted Purdue source, keep it.
    - Otherwise (national feeds like Yahoo / ESPN / CBS / etc.),
      only keep it if it explicitly mentions Purdue (mentions_purdue_text).
    """
    src = story.get("source", "")
    title = story.get("title", "")
    snippet = story.get("snippet", "")

    # Always keep insiders
    if is_trusted_purdue_source(src):
        return True

    # For national feeds, require that it actually mentions Purdue
    if mentions_purdue_text(title, snippet):
        return True

    # Otherwise drop (goodbye random Tennessee/Syracuse/UConn blurbs)
    return False


# -------- Collect + save --------
def load_sources():
    try:
        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("sources", [])
    except Exception as e:
        print("failed to read sources.json", e)
        return []


def collect_all():
    """
    - Pull all sources
    - Parse feed entries
    - Filter with should_keep_story()
    - Score & sort
    - Trim to 20
    - Stamp collected_at
    """
    sources = load_sources()
    raw_items = []

    for src in sources:
        if src.get("type") != "rss":
            continue
        url = src.get("url")
        if not url:
            continue

        xml_bytes = http_get(url)
        parsed_items = parse_rss(xml_bytes, src.get("name", ""))
        raw_items.extend(parsed_items)

    # Filter out irrelevant national chatter
    filtered = [it for it in raw_items if should_keep_story(it)]

    # Score + sort (higher score first; tie-break newer first)
    for it in filtered:
        it["score"] = score_story(it)

    def sort_key(item):
        published_ts = 0
        try:
            published_ts = datetime.datetime.fromisoformat(
                item.get("published", "").replace("Z", "")
            ).timestamp()
        except Exception:
            published_ts = 0
        return (item.get("score", 0), published_ts)

    filtered.sort(key=sort_key, reverse=True)

    # Cap at 20
    filtered = filtered[:20]

    # Stamp collected_at for header badge
    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for it in filtered:
        it["collected_at"] = now_iso

    return filtered


def save_items(items):
    ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {"items": items}
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def main():
    stories = collect_all()

    if not stories:
        # fallback: keep whatever was already in items.json so page isn't empty
        print("No new Purdue stories after filter. Using previous items.json.")
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
