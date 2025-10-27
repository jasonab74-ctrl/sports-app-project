#!/usr/bin/env python3
"""
tools/collect.py

Purdue Men's Basketball collector with tiered relevance.

Tiers:
 A. Trusted Purdue sources  => ALWAYS KEEP (score very high)
 B. Explicit Purdue mentions => KEEP (score high)
 C. Opponent / game context that is clearly about Purdue playing someone
    (e.g. "Kentucky's win over No. 1 Purdue") => KEEP (score medium)
 D. Generic college hoops with no Purdue angle => DROP

This gets us volume without letting Yahoo drown us in random ACC/SEC stories.
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
    Parse feed entries into normalized dicts.
    """
    out = []
    if not xml_bytes:
        return out

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    # RSS or Atom
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


# -------- Relevance logic --------

TRUSTED_KEYWORDS = [
    # if the source contains ANY of these, it's basically Purdue-focused
    "goldandblack",
    "on3",
    "247sports",
    "purdue athletics",
    "si purdue",
    "sports illustrated purdue",
    "usa today purdue",
    "usa today boilermakers",
]

# Clearly Purdue-related terms / people
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
    "west lafayette"
]

# Basketball context words. Not strictly required,
# but they help boost relevance scoring.
HOOPS_TERMS = [
    "basketball",
    "men's basketball",
    "mens basketball",
    "men’s basketball",
    "mbb",
    "backcourt",
    "guard play",
    "point guard",
    "frontcourt",
    "rotation",
    "starting lineup",
    "3-point",
    "three-point",
    "ncaa tournament",
    "march madness",
    "big ten",
    "final four"
]

def is_trusted_source(source):
    """Return True if this is one of our Purdue-heavy/insider sources."""
    if not source:
        return False
    s = source.lower()
    return any(key in s for key in TRUSTED_KEYWORDS)

def mentions_purdue(title, snippet):
    """Return True if title/snippet clearly reference Purdue, Painter, Boilers, etc."""
    blob = f"{title} {snippet}".lower()
    return any(term in blob for term in PURDUE_TERMS)

def is_game_context_about_purdue(title, snippet):
    """
    Tier C:
    Return True if this looks like game context where Purdue is on one side,
    even if the article is framed from the opponent's POV.

    Examples we WANT:
      "5 risers in Kentucky’s impressive exhibition victory over No. 1 Purdue"
    That's still actually Purdue-related.

    We'll look for patterns like:
    - 'over Purdue'
    - 'vs Purdue'
    - 'against Purdue'
    - 'win over No. 1 Purdue'
    - '#1 Purdue' / 'No. 1 Purdue'

    We'll also allow 'No. 1 Purdue' / 'top-ranked Purdue' even without "Purdue" twice.
    """
    blob = f"{title} {snippet}".lower()

    triggers = [
        "purdue",
        "no. 1 purdue",
        "no.1 purdue",
        "number 1 purdue",
        "top-ranked purdue",
        "top ranked purdue",
        "vs purdue",
        "vs. purdue",
        "against purdue",
        "over purdue",
        "over no. 1 purdue",
        "over no.1 purdue",
        "over number 1 purdue"
    ]

    # this is looser than mentions_purdue(): even if Purdue only appears
    # as the opponent in the framing, we keep it.
    return any(t in blob for t in triggers)

def obvious_other_sport(title, snippet):
    """
    We don't want Purdue football or Tennessee football or whatever.
    If it's clearly football/baseball/etc, drop the score.
    """
    blob = f"{title} {snippet}".lower()
    bad_sports = [
        "football",
        "quarterback", "qb",
        "wide receiver", "running back", "touchdown",
        "field goal", "kickoff",
        "baseball", "softball", "volleyball",
        "soccer", "wrestling", "golf", "track and field"
    ]
    return any(term in blob for term in bad_sports)


def relevance_tier(story):
    """
    Return an integer tier:
      3 = Trusted Purdue source (Tier A)
      2 = Explicit Purdue reference (Tier B)
      1 = Opponent framing but clearly about Purdue game/result (Tier C)
      0 = Everything else (Tier D / ignore)

    We also reject obvious non-basketball sports by forcing 0.
    """
    src = story.get("source", "") or ""
    ttl = story.get("title", "") or ""
    snip = story.get("snippet", "") or ""

    if obvious_other_sport(ttl, snip):
        return 0  # football/baseball/etc. out

    # Tier A
    if is_trusted_source(src):
        return 3

    # Tier B
    if mentions_purdue(ttl, snip):
        return 2

    # Tier C
    if is_game_context_about_purdue(ttl, snip):
        return 1

    # Tier D
    return 0


def score_story(story):
    """
    Score a story for ordering within the final feed.
    Higher is better.
    We'll base it mostly on tier + hoops-specific language.
    """
    ttl = story.get("title", "") or ""
    snip = story.get("snippet", "") or ""
    blob = f"{ttl} {snip}".lower()

    tier = relevance_tier(story)
    score = tier * 10  # Tier 3 = 30 pts, Tier 2 = 20 pts, Tier 1 = 10 pts

    # Boost if clearly hoops talk
    if any(term in blob for term in HOOPS_TERMS):
        score += 2

    # Tiny bump if specifically says "Purdue" etc.
    if mentions_purdue(ttl, snip):
        score += 2

    return score


# -------- Pipeline --------

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
    Fetch all feeds, parse, tag with tier/score,
    keep tier >=1, sort, limit 20, timestamp.
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

    # Filter: only keep Tier >=1
    kept = []
    for it in raw_items:
        tier = relevance_tier(it)
        if tier >= 1:
            it["tier"] = tier
            it["score"] = score_story(it)
            kept.append(it)

    # Sort: higher score first, then newer first
    def sort_key(item):
        # published timestamp to float for tie-break
        published_ts = 0
        try:
            published_ts = datetime.datetime.fromisoformat(
                item.get("published", "").replace("Z", "")
            ).timestamp()
        except Exception:
            published_ts = 0
        return (item.get("score", 0), published_ts)

    kept.sort(key=sort_key, reverse=True)

    # Cap at 20 (this should bring back volume)
    kept = kept[:20]

    # Add collected_at timestamp for header badge
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
        # fallback so site isn't blank
        print("No stories matched (after tier filter). Using previous items.json.")
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
