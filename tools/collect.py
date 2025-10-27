#!/usr/bin/env python3
import json, re, html, hashlib, datetime
from datetime import timezone

# -----------------
# CONFIG
# -----------------

MAX_ITEMS = 50  # we’ll dedupe + sort and front-end will slice top 20

TRUSTED_SOURCES = [
    "GoldandBlack.com",
    "On3 Purdue Basketball",
    "247Sports Purdue Basketball",
    "Purdue Athletics MBB",
    "ESPN College Basketball",
    "ESPN Purdue MBB",
    "Yahoo Sports College Basketball",
    "CBS Sports College Basketball",
    "The Field of 68",
    "SI Purdue Basketball",
    "USA Today Purdue Boilermakers",
]

PURDUE_KEYWORDS = [
    "purdue",
    "boilermaker",
    "boilermakers",
    "boiler ball",
    "boilerball",
    "painter",
    "matt painter",
    "braden smith",
    "zach edey",
    "west lafayette",
    "purdue men's basketball",
    "purdue basketball",
    "purdue mbb",
]

# -----------------
# HELPERS
# -----------------

def norm_text(t: str) -> str:
    if not t:
        return ""
    # decode html entities like &#39; etc.
    t = html.unescape(t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

def score_article(a):
    """
    Basic relevance score:
    - +5 if source is trusted
    - +X for Purdue keywords in title/snippet
    - slight bump if title mentions Purdue directly
    """
    score = 0
    src = (a.get("source") or "").lower()

    if a.get("source") in TRUSTED_SOURCES:
        score += 5

    title = (a.get("title") or "").lower()
    snip  = (a.get("snippet") or "").lower()

    # keyword hits
    for kw in PURDUE_KEYWORDS:
        if kw in title or kw in snip:
            score += 3

    # strong Purdue direct mention
    if "purdue" in title:
        score += 4

    # small recency bump (more recent -> higher)
    pub = a.get("published") or ""
    try:
        dt = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00"))
        age_minutes = (datetime.datetime.now(timezone.utc) - dt).total_seconds() / 60.0
        # newer -> less minutes -> bigger bump
        if age_minutes < 60:
            score += 2
        elif age_minutes < 6 * 60:
            score += 1
    except Exception:
        pass

    return score

def to_iso_or_blank(published_raw: str) -> str:
    """
    Try hard to normalize a published timestamp to ISO 8601 with Z.
    If we can't, return "" so the front-end won't show 'Invalid Date'.
    """
    if not published_raw:
        return ""

    # if it's already close to iso
    try:
        dt = datetime.datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        pass

    # try some common RSS/date formats:
    # Example: "Mon, 27 Oct 2025 13:45:00 GMT"
    rss_match = re.match(
        r"[A-Z][a-z]{2},\s+(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})\s+(\d\d:\d\d:\d\d)",
        published_raw
    )
    if rss_match:
        day, mon_abbr, year, hms = rss_match.groups()
        mon_map = {
            "Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
            "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12
        }
        if mon_abbr in mon_map:
            try:
                dt = datetime.datetime.strptime(
                    f"{year}-{mon_map[mon_abbr]:02d}-{int(day):02d} {hms}",
                    "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
                return dt.isoformat().replace("+00:00","Z")
            except Exception:
                pass

    # couldn't parse
    return ""

def article_key_for_dedupe(a):
    """
    We'll dedupe using URL (strong) and also normalized title as backup.
    """
    url = a.get("url","").strip().lower()
    title = norm_text(a.get("title","")).lower()
    combo = url + "||" + title
    return hashlib.sha1(combo.encode("utf-8")).hexdigest()

# -----------------
# FETCH/BUILD DATA
# -----------------

def fetch_all_sources():
    """
    IMPORTANT NOTE:
    In your real repo, you're already fetching feeds from Yahoo, ESPN, etc.
    I'm not reimplementing network fetches here because that part is working.

    Instead, I'm assuming you already built a `raw_items` list like:
    [
      {
        "source": "...",
        "title": "...",
        "snippet": "...",
        "url": "...",
        "published": "...",
      },
      ...
    ]

    So here we'll just say `return raw_items`.
    """

    # You already have this logic in your working collector (requests, parsing, etc.).
    # Keep that part. Just make sure you return the list in this shape.

    # PLACEHOLDER: replace this block with your existing aggregation result.
    # -------------------------------------------------
    raw_items = []  # <-- your current scraped items list
    # -------------------------------------------------

    return raw_items


def main():
    raw_items = fetch_all_sources()

    cleaned = []
    for art in raw_items:
        cleaned.append({
            "source": norm_text(art.get("source","")),
            "title": norm_text(art.get("title","")),
            "snippet": norm_text(art.get("snippet","")),
            "url": art.get("url","").strip(),
            "published": to_iso_or_blank(art.get("published","")),
        })

    # de-dupe
    seen = set()
    deduped = []
    for a in cleaned:
        k = article_key_for_dedupe(a)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(a)

    # score + sort, highest score first
    scored = []
    for a in deduped:
        scored.append((score_article(a), a))
    scored.sort(key=lambda x: x[0], reverse=True)

    final_items = [a for (_, a) in scored][:MAX_ITEMS]

    out = {
        "items": final_items,
        "collected_at": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    }

    with open("static/teams/purdue-mbb/items.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)


if __name__ == "__main__":
    main()