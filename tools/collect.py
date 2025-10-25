#!/usr/bin/env python3
import os
import re
import json
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import requests
import feedparser
import yaml

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

MAX_AGE_DAYS = 3      # rolling freshness window
TOP_N = 20            # how many we keep in the final list

FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PurdueMBBFeedBot/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SOURCE_CANON = {
    "hammer and rails": "Hammer & Rails",
    "hammer & rails": "Hammer & Rails",
    "hammerandrails": "Hammer & Rails",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "journal courier": "Journal & Courier",

    "goldandblack": "GoldandBlack",
    "gold and black": "GoldandBlack",
    "goldandblack.com": "GoldandBlack",
    "goldandblack (rivals)": "GoldandBlack",

    "on3 purdue": "On3 Purdue",
    "on3": "On3 Purdue",

    "espn": "ESPN",
    "espn purdue": "ESPN",

    "cbs sports": "CBS Sports",
    "cbs": "CBS Sports",

    "yahoo sports": "Yahoo Sports",
    "yahoo! sports": "Yahoo Sports",
    "yahoo": "Yahoo Sports",

    "field of 68": "Field of 68",
    "fieldof68": "Field of 68",

    "purdue sports": "PurdueSports",
    "purduesports.com": "PurdueSports",
    "purduesports": "PurdueSports",
}

# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def canon_source(raw):
    """Map raw source/feed title to a nice display label."""
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())

def canonical_url(url):
    """
    Normalize URL for dedupe:
    - lowercase host
    - strip query + fragment
    """
    if not url:
        return ""
    p = urlparse(url)
    clean = p._replace(
        netloc=p.netloc.lower(),
        query="",
        fragment="",
    )
    return urlunparse(clean)

def parse_date(entry):
    """
    Extract a datetime (UTC) from feedparser entry.
    We try published_parsed / updated_parsed / created_parsed.
    Fallback = now().
    """
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def normalize_item(source_name, entry):
    """
    Convert a feedparser entry into our canonical story object.
    NOTE: We are NOT including images anymore.
    {
        "title": ...,
        "link": ...,
        "source": ...,
        "date": <iso8601 UTC>
    }
    """
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    pub_dt = parse_date(entry)

    return {
        "title": title,
        "link": link,
        "source": canon_source(source_name),
        "date": pub_dt.isoformat(),  # keep UTC ISO8601
    }

def looks_like_football(text):
    """
    If it's clearly football, we toss it.
    We're trying to stick to Purdue men's basketball.
    """
    if not text:
        return False
    t = text.lower()

    football_terms = [
        "football",
        "qb", "quarterback",
        "touchdown", "wide receiver",
        "linebacker", "safety", "defensive coordinator",
        "ryan walters", "coach walters", "walters'",
    ]

    return any(term in t for term in football_terms)

def is_relevant_purdue(item):
    """
    Keep:
    - must mention 'purdue' or 'boilermaker(s)'
    - must NOT look like football content
    """
    blob = f"{item.get('title','')} {item.get('source','')}".lower()

    if not any(w in blob for w in ["purdue", "boilermaker", "boilermakers"]):
        return False

    if looks_like_football(blob):
        return False

    return True

def dedupe(items):
    """
    Deduplicate stories by URL or near-duplicate title.
    We keep the first occurrence (which will be newest after sorting).
    """
    out = []
    seen_urls = set()

    def similar_titles(a, b):
        # quick overlap heuristic: if 80%+ of the words match, call them dup
        aw = set(a.lower().split())
        bw = set(b.lower().split())
        if not aw or not bw:
            return False
        inter = len(aw & bw)
        bigger = max(len(aw), len(bw))
        ratio = inter / bigger if bigger else 0.0
        return ratio >= 0.8

    for it in items:
        url_key = canonical_url(it.get("link", ""))

        # direct URL dup
        if url_key and url_key in seen_urls:
            continue

        # fuzzy title dup
        t = it.get("title", "")
        dup = False
        for kept in out:
            if similar_titles(t, kept.get("title", "")):
                dup = True
                break

        if dup:
            continue

        out.append(it)
        if url_key:
            seen_urls.add(url_key)

    return out

def atomic_write_json(path, data_obj):
    """
    Safe write to disk (temp file + rename)
    so GitHub Actions doesn't half-write.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=os.path.dirname(path),
        encoding="utf-8"
    ) as tmp:
        json.dump(data_obj, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

# -------------------------------------------------------------------
# CORE
# -------------------------------------------------------------------

def collect_team(team_slug, feeds_for_team, out_path):
    """
    team_slug: e.g. "purdue-mbb"
    feeds_for_team: list of {name: "...", url: "..."} dicts from feeds.yaml
    out_path: where we write: static/teams/<team_slug>/items.json
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)

    raw_items = []

    # pull entries from every configured feed for this team
    for feed_def in feeds_for_team:
        source_name = feed_def.get("name", "Source")
        url = feed_def.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        # up to ~60 entries per feed, usually way more than enough
        for entry in parsed.entries[:60]:
            item = normalize_item(source_name, entry)

            # age filter
            try:
                dt = datetime.fromisoformat(item["date"])
            except Exception:
                dt = now

            if dt < cutoff:
                continue

            raw_items.append(item)

    # relevance (Purdue mention + not football)
    filtered = [it for it in raw_items if is_relevant_purdue(it)]

    # newest first
    filtered.sort(
        key=lambda i: datetime.fromisoformat(i["date"]),
        reverse=True,
    )

    # dedupe out repeats / rewrites
    deduped = dedupe(filtered)

    # limit to top N
    top_items = deduped[:TOP_N]

    payload = {
        "team": team_slug,
        "updated": now.isoformat(),
        "items": top_items,
    }

    atomic_write_json(out_path, payload)
    print(f"[OK] wrote {len(top_items)} items to {out_path}")

def main():
    """
    - load src/feeds.yaml
    - choose teams from $TEAMS env or all keys in feeds.yaml
    - collect + write items.json for each team
    """
    with open("src/feeds.yaml", "r", encoding="utf-8") as f:
        feeds_by_team = yaml.safe_load(f)

    teams_env = os.environ.get("TEAMS", "").strip()
    if teams_env:
        teams = [t.strip() for t in teams_env.split(",") if t.strip()]
    else:
        teams = list(feeds_by_team.keys())

    if not teams:
        raise SystemExit("No teams configured in feeds.yaml or TEAMS env var")

    for team in teams:
        if team not in feeds_by_team:
            print(f"[WARN] {team} not in feeds.yaml, skipping")
            continue

        out_path = f"static/teams/{team}/items.json"
        collect_team(team, feeds_by_team[team], out_path)

if __name__ == "__main__":
    main()