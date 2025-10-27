#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball news collector.

Priorities:
1. Purdue-first: Painter, Purdue, Braden Smith, "No. 1 Purdue", etc.
2. Opponent/game context about Purdue ("Kentucky's win over No. 1 Purdue").
3. Big Ten / Top 25 / title contender / March Madness talk that clearly includes Purdue.
4. High-level national men's college hoops context from legit national outlets
   (ESPN / CBS / Yahoo CBB) to keep the page feeling alive,
   *only if it's clearly men's college basketball content*.

Still BLOCK:
- Football / baseball / other sports.
- Random hyper-local stuff about some unrelated ACC team that never touches Purdue,
  unless it's coming from a national outlet and obviously men's hoops relevant
  (that's our new Tier 0.6).

Tiers:
 3.0 Purdue-ish source brand (Purdue Athletics MBB, CBS Sports Purdue Boilermakers, etc.)
 2.0 Explicit Purdue mention (Purdue / Boilermakers / Matt Painter / Braden Smith / etc.)
 1.5 Big-picture national/B1G/contender talk WITH Purdue mentioned
 1.0 Opponent recap clearly about Purdue ("victory over No. 1 Purdue")
 0.8 Big Ten / Top 25 / Final Four / March Madness / title race,
     even if Purdue name didn't make the teaser
 0.6 National men's college hoops context from trusted national outlets (ESPN / CBS / Yahoo CBB)
     that is clearly men's basketball talk, used as volume padding
 0.0 Drop

We keep tier >= 0.6
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

# Basketball-ish language
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

# Trusted national outlets for filler Tier 0.6
NATIONAL_OUTLETS = [
    "yahoo sports college basketball",
    "espn",
    "espn college basketball",
    "cbs sports college basketball",
    "cbs sports",
    "yahoo sports"
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
    Soft catch: Big Ten / Top 25 / March Madness / Final Four conversation
    even if Purdue wasn't literally named in the teaser we saw.
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


def is_from_national_outlet(src: str) -> bool:
    """
    Check if story came from ESPN / CBS Sports / Yahoo Sports College Basketball, etc.
    These are allowed to be low-priority filler.
    """
    if not src:
        return False
    s = src.lower()
    return any(n in s for n in NATIONAL_OUTLETS)


def looks_like_mens_hoops(blob: str) -> bool:
    """
    Require basketball language so we don't pull random admin/AD news.
    """
    return any(term in blob for term in HOOPS_TERMS)


def relevance_tier(story):
    """
    Return numeric tier:

    3.0 Purdue-ish source branding (Purdue Athletics MBB, 'Purdue Boilermakers', etc.)
    2.0 Explicit Purdue mention (Purdue / Boilermakers / Painter / Braden Smith / etc.)
    1.5 National/B1G/contender talk WITH Purdue mentioned
    1.0 Opponent recap clearly about Purdue ("victory over No. 1 Purdue")
    0.8 Big Ten / Top 25 / Final Four / March Madness / title race *even without*
        Purdue name in the teaser
    0.6 High-level men's college hoops context from a trusted national outlet
        (ESPN/CBS/Yahoo CBB) that clearly sounds like men's basketball
    0.0 Drop

    Anything that smells like football/baseball/etc. is 0.0 immediately.
    """
    b = blob_for(story)
    src = story.get("source", "") or ""

    if is_obviously_other_sport(b):
        return 0.0

    # 3.0: Purdue-flavored source name
    if is_trusted_source(src):
        return 3.0

    # 2.0: direct Purdue mention
    if mentions_purdue_direct(b):
        return 2.0

    # 1.5: national/B1G/contender talk explicitly mentioning Purdue
    if is_big_context_that_mentions_purdue(b):
        return 1.5

    # 1.0: opponent writes about Purdue game/result
    if is_game_context_about_purdue(b):
        return 1.0

    # 0.8: Big Ten / Top 25 / March Madness style convo
    if is_big_ten_or_top25_context(b):
        return 0.8

    # 0.6: national men's hoops filler from ESPN/CBS/Yahoo CBB
    if is_from_national_outlet(src) and looks_like_mens_hoops(b):
        return 0.6

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
        0.8: 8.0,
        0.6: 6.0
    }.get(tier_val, 0.0)

    score = base_score

    # small bump for hoops vocab
    if looks_like_mens_hoops(b):
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
    Fetch feeds -> parse -> tier/score -> keep tier >= 0.6
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
        if tval >= 0.6:
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