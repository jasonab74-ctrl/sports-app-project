#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball collector with tiered, volume-friendly relevance.

Tiers:
 3 = Tier A: Trusted Purdue sources (GoldandBlack, On3 Purdue, etc.)
     Always include. Score highest.

 2 = Tier B: Direct Purdue focus (Purdue / Boilermakers / Painter / etc. clearly
     in headline/snippet). Include. High score.

 1.5 = Tier B-Plus: National / Big Ten / Top 25 context articles that DO mention
     Purdue somewhere in the teaser/snippet/headline, even if it's not ONLY
     about Purdue. This boosts volume while staying relevant.
     Example: "10 key questions for the 2025-26 men's season" where one of
     the questions is "Can Purdue finally get over the hump?"

 1 = Tier C: Opponent-framed recap of a Purdue game or result
     ("5 risers in Kentucky's impressive exhibition victory over No. 1 Purdue").
     Still relevant. Include. Medium score.

 0 = Tier D: Generic CBB pieces with no Purdue angle OR non-basketball sports.
     Drop.

Output:
- top ~20 highest scored + most recent stories
- writes static/teams/purdue-mbb/items.json
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
    Parse feed entries into normalized dicts for downstream logic.
    """
    out = []
    if not xml_bytes:
        return out

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    # Support RSS ("channel"/"item") and Atom ("entry")
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


# -------- relevance signals --------

TRUSTED_KEYWORDS = [
    # If source includes any of these, it's basically Purdue-specific / insider.
    "goldandblack",
    "on3",
    "247sports",
    "purdue athletics",
    "si purdue",
    "sports illustrated purdue",
    "usa today purdue",
    "usa today boilermakers",
]

PURDUE_TERMS = [
    "purdue",
    "boilermaker",
    "boilermakers",
    "boilers",
    "matt painter",
    "painter",
    "braden smith",
    "fletcher loyer",
    "zach edey",
    "mackey",
    "west lafayette",
    "no. 1 purdue",
    "no.1 purdue",
    "number 1 purdue",
    "top-ranked purdue",
    "top ranked purdue"
]

# language that suggests we're talking hoops not football, baseball, etc.
HOOPS_TERMS = [
    "basketball",
    "men's basketball",
    "mens basketball",
    "men’s basketball",
    "mbb",
    "guard",
    "backcourt",
    "point guard",
    "frontcourt",
    "rotation",
    "starting lineup",
    "3-point",
    "three-point",
    "ncaa tournament",
    "march madness",
    "big ten",
    "final four",
    "exhibition",
    "scrimmage"
]

BAD_SPORT_TERMS = [
    "football",
    "quarterback", "qb",
    "wide receiver", "running back",
    "touchdown", "field goal", "kickoff",
    "baseball", "softball", "volleyball",
    "soccer", "wrestling", "golf",
    "track and field", "track & field"
]


def text_blob(story):
    return f"{story.get('title','')} {story.get('snippet','')}".lower()


def is_trusted_source(src: str) -> bool:
    """
    Tier 3 (A): sources we basically trust as Purdue-focused.
    """
    if not src:
        return False
    s = src.lower()
    return any(key in s for key in TRUSTED_KEYWORDS)


def mentions_purdue_direct(blob: str) -> bool:
    """
    Tier 2 (B): Purdue clearly the subject.
    """
    return any(term in blob for term in PURDUE_TERMS)


def is_game_context_about_purdue(blob: str) -> bool:
    """
    Tier 1 (C): Opponent-framed article, but specifically referencing
    playing Purdue / beating Purdue / vs Purdue.
    Still Purdue-relevant.
    """
    triggers = [
        "vs purdue",
        "vs. purdue",
        "against purdue",
        "over purdue",
        "over no. 1 purdue",
        "over no.1 purdue",
        "over number 1 purdue",
        "victory over no. 1 purdue",
        "victory over purdue",
        "win over no. 1 purdue",
        "win over purdue",
        "beat purdue",
        "beats purdue",
        "upset purdue",
        "upsets purdue",
        "over #1 purdue",
        "over # 1 purdue",
        "#1 purdue",
        "# 1 purdue"
    ]
    return any(t in blob for t in triggers)


def is_big_context_that_mentions_purdue(blob: str) -> bool:
    """
    Tier 1.5 (C+): National / Big Ten / Top 25 preview / questions-style article
    that includes Purdue somewhere in the chatter — not ONLY Purdue, but Purdue
    shows up as part of the storyline.

    This is how we get volume back: if they even *touch* Purdue in a
    national-season-preview style piece, we'll keep it.
    """
    # must mention Purdue at least once
    if not mentions_purdue_direct(blob):
        return False

    # and should sound like national/big-picture talk
    context_terms = [
        "top 25",
        "top-25",
        "top25",
        "preseason questions",
        "key questions",
        "season preview",
        "ahead of the season",
        "who can win it all",
        "title race",
        "national title hopes",
        "final four contenders",
        "big ten race",
        "big ten title",
        "conference race",
        "power rankings",
        "rankings",
        "poll",
        "ap poll"
    ]
    return any(t in blob for t in context_terms)


def is_obviously_other_sport(blob: str) -> bool:
    """
    Strong kill switch: don't accidentally let Purdue football or
    random volleyball in here.
    """
    return any(term in blob for term in BAD_SPORT_TERMS)


def relevance_tier(story):
    """
    Return numeric "tier" – higher means more Purdue-relevant.

    3.0 = Tier A: trusted Purdue source (GoldandBlack, etc.)
    2.0 = Tier B: direct Purdue focus (Purdue / Painter / Boilermakers clearly the subject)
    1.5 = Tier B+: national piece that talks about Purdue as part of top-25 / Big Ten / title convo
    1.0 = Tier C: game/opponent framing where Purdue is the opponent discussed
    0.0 = Tier D: irrelevant

    If it's obviously another sport, force 0.0.
    """
    blob = text_blob(story)

    if is_obviously_other_sport(blob):
        return 0.0

    if is_trusted_source(story.get("source", "")):
        return 3.0

    if mentions_purdue_direct(blob):
        # direct Purdue = 2.0, but could also qualify for 1.5,
        # so 2.0 wins already
        return 2.0

    if is_big_context_that_mentions_purdue(blob):
        # national narrative that mentions Purdue specifically
        return 1.5

    if is_game_context_about_purdue(blob):
        return 1.0

    return 0.0


def score_story(story):
    """
    Turn tier + hoops-iness into a numeric score.
    Higher score sorts earlier.
    """
    blob = text_blob(story)

    tier_val = relevance_tier(story)
    score = tier_val * 10.0  # Tier 3 => 30, Tier 2 => 20, Tier 1.5 => 15, Tier 1 => 10

    # bump if it clearly sounds like hoops (rotation, backcourt, etc)
    if any(term in blob for term in HOOPS_TERMS):
        score += 2.0

    # small bump for explicit Purdue mention
    if mentions_purdue_direct(blob):
        score += 2.0

    return score


# -------- pipeline --------

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
    Fetch feeds -> parse -> tier -> filter tier>=1 -> score -> sort -> cap 20
    -> write collected_at
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

    # Keep only tier >= 1.0 (C, C+, B, A)
    kept = []
    for it in raw_items:
        tier_val = relevance_tier(it)
        if tier_val >= 1.0:
            it["tier"] = tier_val
            it["score"] = score_story(it)
            kept.append(it)

    # Sort by score desc, then newest first
    def sort_key(item):
        # parse published -> timestamp
        published_ts = 0
        try:
            published_ts = datetime.datetime.fromisoformat(
                item.get("published", "").replace("Z", "")
            ).timestamp()
        except Exception:
            published_ts = 0
        return (item.get("score", 0.0), published_ts)

    kept.sort(key=sort_key, reverse=True)

    # Cap at 20 to keep UI tight
    kept = kept[:20]

    # Stamp current collected time for header badge
    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for it in kept:
        it["collected_at"] = now_iso

    return kept


def save_items(items):
    ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {"items": items}
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def main():
    stories = collect_all()

    if not stories:
        # Fallback so the page isn't blank if for some reason everything filtered out.
        print("No stories matched after filter. Using previous items.json.")
        try:
            raw = ITEMS_PATH.read_text("utf-8")
            current_json = json.loads(raw)
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
