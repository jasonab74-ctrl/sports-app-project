#!/usr/bin/env python3
"""
tools/collect.py

Locked-in Purdue Men's Basketball feed.

What we INCLUDE now:
 - Tier 3.0: Trusted Purdue-ish sources (Purdue Athletics MBB, Purdue team feeds, etc.)
 - Tier 2.0: Direct Purdue focus (Purdue / Boilermakers / Painter / Braden Smith / etc.)
 - Tier 1.5: National / Big Ten / Top 25 / contender talk that explicitly mentions Purdue
 - Tier 1.0: Opponent recap that is clearly about a game vs Purdue (“over No. 1 Purdue”, etc.)

What we DROP now:
 - The old Tier 0.5 "generic college basketball" filler.
   That was giving you Memphis/Tennessee/Arizona State/etc. That’s gone.

Result:
 - Fewer total cards, but way higher purity.
 - Top stories should almost all name Purdue either in title or snippet or be
   opponent talking specifically about beating/playing Purdue.

Pipeline:
 - Fetch RSS sources from static/sources.json
 - Score and sort by relevance + recency
 - Keep top 20
 - Write static/teams/purdue-mbb/items.json
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

    # RSS-style
    channel = root.find("channel")
    if channel is not None:
        item_nodes = channel.findall("item")
    else:
        # Atom-style
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


# -------- relevance helpers --------

TRUSTED_KEYWORDS = [
    # Purdue-focused / insider style brands
    "purdue athletics",
    "purdue boilermakers",
    "purdue boilermaker",
    "boilermakers",
    "boilermaker",
    "purdue mbb",
    "purdue men's basketball",
    "purdue men’s basketball",
    "purdue men's hoops",
    "purdue men's basketball news",
    "purdue boilermakers mbb",
    "espn purdue boilermakers mbb",
    "cbs sports purdue boilermakers",
    "goldandblack",
    "on3",
    "247sports",
    "si purdue",
    "sports illustrated purdue",
    "usa today purdue",
    "usa today boilermakers"
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
    "top ranked purdue",
    "#1 purdue",
    "# 1 purdue"
]

HOOPS_TERMS = [
    # language that screams men's college hoops
    "basketball",
    "men's basketball",
    "mens basketball",
    "men’s basketball",
    "mbb",
    "backcourt",
    "point guard",
    "guard play",
    "frontcourt",
    "rotation",
    "starting lineup",
    "3-point",
    "three-point",
    "exhibition",
    "scrimmage",
    "ncaa tournament",
    "march madness",
    "big ten",
    "final four",
    "preseason",
    "season preview",
    "title race",
    "contender",
    "contenders",
    "power rankings",
    "ranking",
    "rankings",
    "poll",
    "ap poll"
]

BAD_SPORT_TERMS = [
    # anything that looks like not men's hoops
    "football",
    "quarterback", "qb",
    "wide receiver", "running back",
    "touchdown", "field goal", "kickoff",
    "baseball", "softball", "volleyball",
    "soccer", "wrestling", "golf",
    "track and field", "track & field"
]


def blob_for(story):
    return f"{story.get('title','')} {story.get('snippet','')}".lower()


def is_trusted_source(src: str) -> bool:
    """
    If the source name itself sounds like it's Purdue men's basketball focused
    (Purdue Athletics MBB, CBS Sports Purdue Boilermakers, etc.)
    treat as max relevance.
    """
    if not src:
        return False
    s = src.lower()
    return any(key in s for key in TRUSTED_KEYWORDS)


def mentions_purdue_direct(blob: str) -> bool:
    """
    Clearly Purdue / Painter / Boilers / etc.
    """
    return any(term in blob for term in PURDUE_TERMS)


def is_game_context_about_purdue(blob: str) -> bool:
    """
    Opponent-side recap of a Purdue game or result.
    e.g. "5 risers in Kentucky's impressive exhibition victory over No. 1 Purdue"
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
        "upsets purdue"
    ]
    return any(t in blob for t in triggers)


def is_big_context_that_mentions_purdue(blob: str) -> bool:
    """
    National / Big Ten / Top 25 / contender talk that explicitly mentions Purdue.
    We keep this because it’s relevant to Purdue’s status.
    """
    context_terms = [
        "top 25", "top-25", "top25",
        "preseason questions",
        "key questions",
        "season preview",
        "title race",
        "contender", "contenders",
        "national title hopes",
        "final four contenders",
        "big ten race",
        "big ten title",
        "conference race",
        "power rankings",
        "ranking",
        "rankings",
        "poll",
        "ap poll",
        "march madness",
        "ncaa tournament"
    ]
    if not mentions_purdue_direct(blob):
        return False
    return any(t in blob for t in context_terms)


def is_obviously_other_sport(blob: str) -> bool:
    """
    Kill switch to keep out football/other sports.
    """
    return any(term in blob for term in BAD_SPORT_TERMS)


def relevance_tier(story):
    """
    Return a numeric tier:

    3.0 = Trusted Purdue-ish source by name.
    2.0 = Direct Purdue mention (Purdue / Boilers / Painter / etc.).
    1.5 = Big-picture national/B1G/Top 25 convo that explicitly mentions Purdue.
    1.0 = Opponent recap that is clearly about a Purdue game/result.
    0.0 = Everything else (including generic hoops that doesn't mention Purdue).

    We also immediately kill if this smells like another sport.
    """
    b = blob_for(story)
    src = story.get("source", "") or ""

    if is_obviously_other_sport(b):
        return 0.0

    # Tier 3: source branding itself is Purdue-centric
    if is_trusted_source(src):
        return 3.0

    # Tier 2: headline/snippet clearly about Purdue itself
    if mentions_purdue_direct(b):
        return 2.0

    # Tier 1.5: national/big-ten/top-25 convo that explicitly includes Purdue
    if is_big_context_that_mentions_purdue(b):
        return 1.5

    # Tier 1: opponent writes about beating/playing Purdue
    if is_game_context_about_purdue(b):
        return 1.0

    return 0.0


def score_story(story):
    """
    Convert tier + hoops-y language into numeric score.
    """
    b = blob_for(story)

    tier_val = relevance_tier(story)
    base_score = {
        3.0: 30.0,
        2.0: 20.0,
        1.5: 15.0,
        1.0: 10.0
    }.get(tier_val, 0.0)

    score = base_score

    # small bump for hoops vocab
    if any(term in b for term in HOOPS_TERMS):
        score += 1.0

    # bump again if explicit Purdue mention
    if mentions_purdue_direct(b):
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
    Fetch feeds -> parse -> tier/score -> keep tier >= 1.0
    -> sort -> cap 20 -> timestamp
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

    kept = []
    for it in raw_items:
        tval = relevance_tier(it)
        if tval >= 1.0:
            it["tier"] = tval
            it["score"] = score_story(it)
            kept.append(it)

    # sort by score desc then recency desc
    def sort_key(item):
        try:
            published_ts = datetime.datetime.fromisoformat(
                item.get("published", "").replace("Z", "")
            ).timestamp()
        except Exception:
            published_ts = 0
        return (item.get("score", 0.0), published_ts)

    kept.sort(key=sort_key, reverse=True)

    # cap 20
    kept = kept[:20]

    # timestamp for header badge
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
