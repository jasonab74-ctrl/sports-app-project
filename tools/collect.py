#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball collector with tiered relevance + fallback volume.

Tiers:
 3.0 = Tier A: Trusted Purdue sources (GoldandBlack, On3 Purdue, 247 Purdue, Purdue Athletics MBB, SI Purdue, etc.)
       ALWAYS include. Very high score.

 2.0 = Tier B: Direct Purdue focus. Headline/snippet clearly about Purdue/
       Boilermakers/Matt Painter/etc. Include. High score.

 1.5 = Tier B+: National/Big Ten/Top 25 preview or "who can win it" style piece
       that explicitly *mentions Purdue* in the teaser we can see.
       Include. Medium-high score.

 1.0 = Tier C: Opponent-framed recap clearly about a Purdue game/result
       ("Kentucky's impressive exhibition victory over No. 1 Purdue").
       Include. Medium score.

 0.5 = Tier Fallback: College men's basketball season / Big Ten / Top 25 context
       from trusted national college hoops sources (Yahoo Sports College Basketball,
       CBS Sports College Basketball, ESPN, etc.) that *may not explicitly say
       'Purdue' in the RSS snippet yet*, but is obviously about men's college
       basketball / preseason / contenders.
       We include these LAST so the site never looks empty.
       Low score.

 0.0 = Drop: generic non-Purdue stuff, or non-basketball sports.

We then:
- Fetch RSS sources from static/sources.json
- Score + sort
- Keep top 20
- Save to static/teams/purdue-mbb/items.json
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
    "top ranked purdue",
    "#1 purdue",
    "# 1 purdue",
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
    "top 25",
    "top-25",
    "top25",
    "preseason",
    "season preview",
    "title race",
    "contender",
    "contenders",
    "power rankings",
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

NATIONAL_CBB_SOURCES = [
    # We'll trust these for Tier 0.5 fallback only.
    "yahoo sports college basketball",
    "cbs sports college basketball",
    "espn",
    "espn.com",
    "espn college basketball",
    "the field of 68",
]


def blob_for(story):
    return f"{story.get('title','')} {story.get('snippet','')}".lower()


def is_trusted_source(src: str) -> bool:
    if not src:
        return False
    s = src.lower()
    return any(key in s for key in TRUSTED_KEYWORDS)


def mentions_purdue_direct(blob: str) -> bool:
    return any(term in blob for term in PURDUE_TERMS)


def is_game_context_about_purdue(blob: str) -> bool:
    """
    Opponent-side framing but clearly about Purdue game/result.
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
    ]
    return any(t in blob for t in triggers)


def is_big_context_that_mentions_purdue(blob: str) -> bool:
    """
    National / Big Ten / Top 25 / contender / preseason questions
    AND Purdue is actually referenced.
    """
    context_terms = [
        "top 25", "top-25", "top25",
        "preseason questions",
        "key questions",
        "season preview",
        "ahead of the season",
        "title race",
        "contender", "contenders",
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
    if not mentions_purdue_direct(blob):
        return False
    return any(t in blob for t in context_terms)


def is_generic_college_basketball_story(story):
    """
    Tier 0.5 fallback:
    - Source is a known national men's college basketball feed (Yahoo Sports College Basketball, CBS Sports College Basketball, ESPN, Field of 68, etc.)
    - Text smells like men's college basketball / preseason / rankings / Big Ten / Top 25
    - Even if it *doesn't* explicitly say 'Purdue' in the snippet we got

    We use this as filler so the page doesn't look empty.
    This is bottom-ranked content.
    """
    src = (story.get("source") or "").lower()
    blob = blob_for(story)

    # must be a national CBB source we trust
    if not any(src.startswith(nsrc) or nsrc in src for nsrc in NATIONAL_CBB_SOURCES):
        return False

    # must be about men's college basketball landscape, not football/baseball/etc.
    if any(bad in blob for bad in BAD_SPORT_TERMS):
        return False

    # must include general men's hoops / season framing
    hoops_hits = [term for term in HOOPS_TERMS if term in blob]
    return len(hoops_hits) > 0


def is_obviously_other_sport(blob: str) -> bool:
    return any(term in blob for term in BAD_SPORT_TERMS)


def relevance_tier(story):
    """
    Returns:
      3.0  trusted Purdue source
      2.0  direct Purdue focus
      1.5  national/season/big-picture talk that explicitly mentions Purdue
      1.0  opponent recap clearly about a Purdue game/result
      0.5  generic national men's CBB season talk from a trusted hoops source
      0.0  ignore

    We DO NOT allow football/baseball/etc.
    """
    b = blob_for(story)
    src = story.get("source", "") or ""

    if is_obviously_other_sport(b):
        return 0.0

    # Tier 3.0: always show insiders
    if is_trusted_source(src):
        return 3.0

    # Tier 2.0: clearly Purdue / Boilers / Painter, etc.
    if mentions_purdue_direct(b):
        return 2.0

    # Tier 1.5: national framing that explicitly mentions Purdue in that framing
    if is_big_context_that_mentions_purdue(b):
        return 1.5

    # Tier 1.0: "X beats Purdue / vs Purdue / over Purdue"
    if is_game_context_about_purdue(b):
        return 1.0

    # Tier 0.5: generic national men's CBB from known hoops source
    # (big picture preseason, Big Ten, Top 25, etc.) to pad volume
    if is_generic_college_basketball_story(story):
        return 0.5

    return 0.0


def score_story(story):
    """
    Convert tier + hoops-y vocabulary into numeric score.
    Higher score sorts higher.
    Tier is the main driver:
      Tier 3.0 -> 30 pts
      Tier 2.0 -> 20 pts
      Tier 1.5 -> 15 pts
      Tier 1.0 -> 10 pts
      Tier 0.5 -> 5 pts (our filler floor)
    """
    b = blob_for(story)

    tier_val = relevance_tier(story)
    # base from tier
    base_score = {
        3.0: 30.0,
        2.0: 20.0,
        1.5: 15.0,
        1.0: 10.0,
        0.5: 5.0
    }.get(tier_val, 0.0)

    score = base_score

    # bump for hoops-y talk
    if any(term in b for term in HOOPS_TERMS):
        score += 1.0

    # bump if explicit Purdue mention
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
    Fetch feeds, parse, apply tier calculation, keep tier >= 0.5,
    score, sort, cap 20, timestamp.
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
        tier_val = relevance_tier(it)
        if tier_val >= 0.5:
            it["tier"] = tier_val
            it["score"] = score_story(it)
            kept.append(it)

    # sort by (score desc, then newest first)
    def sort_key(item):
        try:
            published_ts = datetime.datetime.fromisoformat(
                item.get("published", "").replace("Z", "")
            ).timestamp()
        except Exception:
            published_ts = 0
        return (item.get("score", 0.0), published_ts)

    kept.sort(key=sort_key, reverse=True)

    # cap to 20 (enough volume to make page feel full)
    kept = kept[:20]

    # stamp when we pulled
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
        # fallback so page isn't blank
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
