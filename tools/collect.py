#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball news collector.

Goal:
1. Surface Purdue men's basketball stories first.
2. Keep obvious Purdue-adjacent stories (opponents talking about Purdue, "over No. 1 Purdue", etc.).
3. Add controlled "Big Ten / Top 25 / title contender / season outlook" context
   to keep the page from looking empty, even if Purdue isn't literally named
   in the short RSS teaser we got.

Tiers we keep:
 3.0 = Trusted Purdue-ish source by name ("Purdue Athletics MBB", "CBS Sports Purdue Boilermakers", etc.)
 2.0 = Direct Purdue mention (Purdue / Boilermakers / Matt Painter / Braden Smith / etc.)
 1.5 = National/B1G/contender talk that explicitly mentions Purdue ("Can Purdue finally break through in March?")
 1.0 = Opponent/game recap clearly about Purdue ("Kentucky's exhibition win over No. 1 Purdue")
 0.8 = Big Ten / Top 25 / preseason poll / title race / Final Four / March Madness,
       even if the short snippet we saw didn't literally include "Purdue".
       This is our soft catch to keep volume decent.

We DROP everything else:
 - Generic "Memphis roster overhaul"
 - "Texas A&M looks promising"
 - Tennessee/Duke breakdowns that have nothing to do with Purdue
 - Other sports (football, baseball, etc.)

Pipeline:
 - Load RSS sources from static/sources.json
 - Fetch, parse, score, sort
 - Keep tier >= 0.8
 - Cap 20
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

# Names that "sound like" Purdue men's basketball coverage
TRUSTED_KEYWORDS = [
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

# Words that scream "this is Purdue or its core people"
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

# Basketball-y language we like
HOOPS_TERMS = [
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

# Obvious "not men's hoops"
BAD_SPORT_TERMS = [
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
    If the source name itself sounds Purdue-focused,
    treat it as Tier 3.0 high priority.
    """
    if not src:
        return False
    s = src.lower()
    return any(key in s for key in TRUSTED_KEYWORDS)


def mentions_purdue_direct(blob: str) -> bool:
    """
    Headline/snippet explicitly names Purdue / Boilermakers / Painter / etc.
    """
    return any(term in blob for term in PURDUE_TERMS)


def is_game_context_about_purdue(blob: str) -> bool:
    """
    Opponent-side recap of a Purdue game or result.
    Ex: "5 risers in Kentucky's impressive exhibition victory over No. 1 Purdue"
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
    National / Big Ten / Top 25 / contender talk that explicitly
    includes Purdue by name.
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


def is_big_ten_or_top25_context(blob: str) -> bool:
    """
    Soft catch: Big Ten / Top 25 / title contender / March Madness
    talk that *doesn't* explicitly say "Purdue" in the teaser we saw,
    but is still national men's college basketball context.

    This is Tier 0.8: we keep it low priority, just to keep the page
    feeling alive, but it must clearly be men's college basketball
    conversation at a national / Big Ten / ranking / contender level.
    """
    triggers = [
        "big ten", "b1g",
        "top 25", "top-25", "top25",
        "ap poll", "coaches poll", "preseason poll",
        "final four",
        "march madness",
        "ncaa tournament",
        "contenders",
        "title race",
        "season preview",
        "power rankings",
        "ranking", "rankings"
    ]
    return any(t in blob for t in triggers)


def is_obviously_other_sport(blob: str) -> bool:
    """
    We hard reject anything that looks like football/baseball/etc.
    """
    return any(term in blob for term in BAD_SPORT_TERMS)


def relevance_tier(story):
    """
    Return numeric tier:

    3.0 = Source branding sounds Purdue-specific (Purdue Athletics MBB, CBS Sports Purdue Boilermakers, etc.)
    2.0 = Direct Purdue mention (Purdue / Boilermakers / Painter / Braden Smith / etc.)
    1.5 = National/B1G/Top 25/contender talk that explicitly names Purdue
    1.0 = Opponent recap clearly about a Purdue game/result ("victory over No. 1 Purdue")
    0.8 = Big Ten / Top 25 / March Madness / contender framing even if Purdue
          wasn't literally in the teaser text we saw. This is our low-priority filler.
    0.0 = Drop

    Anything that smells like football/baseball/etc. is 0.0 immediately.
    """
    b = blob_for(story)
    src = story.get("source", "") or ""

    if is_obviously_other_sport(b):
        return 0.0

    # 3.0: Purdue-flavored source
    if is_trusted_source(src):
        return 3.0

    # 2.0: direct Purdue mention
    if mentions_purdue_direct(b):
        return 2.0

    # 1.5: national/B1G/contender talk that explicitly includes Purdue
    if is_big_context_that_mentions_purdue(b):
        return 1.5

    # 1.0: opponent writes about Purdue game/result
    if is_game_context_about_purdue(b):
        return 1.0

    # 0.8: generic Big Ten / Top 25 / March Madness conversation (fallback)
    if is_big_ten_or_top25_context(b):
        return 0.8

    return 0.0


def score_story(story):
    """
    Convert tier + hoops-y language into numeric score.
    Higher score sorts higher.
    """
    b = blob_for(story)

    tier_val = relevance_tier(story)
    base_score = {
        3.0: 30.0,
        2.0: 20.0,
        1.5: 15.0,
        1.0: 10.0,
        0.8: 8.0
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
    Fetch feeds -> parse -> tier/score -> keep tier >= 0.8
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
        if tval >= 0.8:
            it["tier"] = tval
            it["score"] = score_story(it)
            kept.append(it)

    # sort by (score desc, recency desc)
    def sort_key(item):
        try:
            published_ts = datetime.datetime.fromisoformat(
                item.get("published", "").replace("Z", "")
            ).timestamp()
        except Exception:
            published_ts = 0
        return (item.get("score", 0.0), published_ts)

    kept.sort(key=sort_key, reverse=True)

    # cap to 20
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
