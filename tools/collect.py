l#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Boilermakers Hub collector (final tweak):
- Expands Insider/Beat Links aggregation
- Keeps robust schedule collection you already approved

Outputs (arrays/objects the site already expects):
  static/data/beat_links.json   -> list[ {title, url, source} ]  (TOP 12)
  static/data/schedule.json     -> { team, updated_at, source, games: [...] }

Design goals:
- Never blank the UI: if fetching fails, keep last-good file.
- All times ISO-8601 UTC for schedule; human-local string included.

Requires (already in collect.yml):
  requests, feedparser, beautifulsoup4, lxml, python-dateutil, pytz
"""

from __future__ import annotations
import json, os, re, sys
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

import requests
import feedparser
from bs4 import BeautifulSoup

try:
    from dateutil import parser as dateutil_parser
except Exception:
    dateutil_parser = None

# ---------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "static", "data")
CONFIG_DIR = os.path.join(ROOT, "static", "config")
os.makedirs(DATA_DIR, exist_ok=True)

TEAM_NAME = "Purdue"
SPORT = "mens-basketball"
PURDUE_SCHEDULE_URL = f"https://purduesports.com/sports/{SPORT}/schedule"
ESPN_SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/2509/schedule"

OUT_SCHEDULE = os.path.join(DATA_DIR, "schedule.json")
OUT_BEATS    = os.path.join(DATA_DIR, "beat_links.json")

# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path: str, obj: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def safe_parse_datetime(text: str) -> Optional[datetime]:
    if not text:
        return None
    try:
        if dateutil_parser:
            dt = dateutil_parser.parse(text)
            if dt.tzinfo is None:
                # assume US/Eastern if naive, then convert to UTC
                from datetime import timedelta
                dt = dt.replace(tzinfo=timezone.utc) - timedelta(hours=4)
            return dt.astimezone(timezone.utc)
        # minimal fallback: YYYY-MM-DD or YYYY-MM-DDTHH:MM
        m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}):(\d{2}))?", text)
        if m:
            y, mo, d = map(int, m.group(1).split("-"))
            if m.group(2):
                hh = int(m.group(2)); mm = int(m.group(3))
                return datetime(y, mo, d, hh, mm, tzinfo=timezone.utc)
            return datetime(y, mo, d, 0, 0, tzinfo=timezone.utc)
    except Exception:
        return None
    return None

def human_local(dt_utc: datetime) -> str:
    # readable string; UI already labels "local"
    try:
        # use platform-appropriate formatting
        return dt_utc.astimezone().strftime("%-m/%-d/%Y, %-I:%M %p local")
    except Exception:
        return dt_utc.astimezone().strftime("%m/%d/%Y, %I:%M %p local")

# ---------------------------------------------------------------------
# BEAT LINKS (expanded)
# ---------------------------------------------------------------------

# Default Purdue-focused sources (you can override/extend via static/config/beat_sources.json)
DEFAULT_BEAT_SOURCES = [
    # Insiders
    "https://www.hammerandrails.com/rss/index.xml",
    "https://goldandblack.com/feed/",
    "https://247sports.com/college/purdue/rss/",
    "https://purdue.rivals.com/rss",
    # Official men's basketball news also qualifies as "insider/beat"
    "https://purduesports.com/rss?path=mbball",
]

# Titles that clearly indicate MBB; we keep this permissive but Purdue-leaning
INCLUDE_HINTS = re.compile(
    r"(purdue|boilermaker|mbb|men['’]?s|basketball|mackey|b1g|big ten)",
    re.I,
)

# Avoid football bleed-through
EXCLUDE_HINTS = re.compile(r"\b(football|cfb|nfl)\b", re.I)

def load_beat_sources() -> List[str]:
    cfg_path = os.path.join(CONFIG_DIR, "beat_sources.json")
    cfg = read_json(cfg_path, [])
    if isinstance(cfg, list) and cfg:
        return cfg
    return DEFAULT_BEAT_SOURCES

def normalize_item(title: str, url: str, source: str) -> Optional[Dict[str, str]]:
    t = (title or "").strip()
    u = (url or "").strip()
    s = (source or "").strip()
    if not t or not u:
        return None
    text = f"{t} {s}"
    if EXCLUDE_HINTS.search(text):
        return None
    # Prefer to include if any hint, but don't be so strict that we return 0
    if not INCLUDE_HINTS.search(text) and "purduesports" not in u and "hammerandrails" not in u and "goldandblack" not in u:
        # low-signal item; allow it but it will sort lower (we don't score here—just filter obvious no's)
        pass
    return {"title": t, "url": u, "source": s}

def fetch_feed(url: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:30]:
            title = (e.get("title") or "").strip()
            link  = (e.get("link") or "").strip()
            if not title or not link:
                continue
            # Try to identify source cleanly
            src = ""
            if "goldandblack" in url:
                src = "Gold and Black"
            elif "hammerandrails" in url:
                src = "Hammer & Rails"
            elif "247sports" in url:
                src = "247Sports (Purdue)"
            elif "rivals.com" in url:
                src = "Rivals (Purdue)"
            elif "purduesports" in url:
                src = "PurdueSports.com"
            else:
                src = (feed.feed.get("title") or "").strip() or url

            it = normalize_item(title, link, src)
            if it:
                items.append(it)
    except Exception as e:
        print(f"[beats] feed error {url}: {e}", file=sys.stderr)
    return items

def fetch_site_front_page(url: str) -> List[Dict[str, str]]:
    """
    Fallback when a site lacks good RSS: scrape a few <a> tags that look like articles.
    """
    items: List[Dict[str, str]] = []
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0 (Actions)"})
        if not r.ok:
            return items
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a[href]")[:200]:
            href = a.get("href") or ""
            text = a.get_text(" ", strip=True)
            if not text or not href:
                continue
            if href.startswith("/"):
                # resolve relative links
                from urllib.parse import urljoin
                href = urljoin(url, href)
            # crude filter for article-ish links
            if any(x in href for x in ("/news", "/article", "/stories", "/posts", "/mbb", "/basketball")):
                it = normalize_item(text, href, url)
                if it:
                    items.append(it)
            if len(items) >= 20:
                break
    except Exception as e:
        print(f"[beats] scrape error {url}: {e}", file=sys.stderr)
    return items

def collect_beats() -> List[Dict[str, str]]:
    sources = load_beat_sources()
    pool: List[Dict[str, str]] = []

    for u in sources:
        got = fetch_feed(u)
        if not got:
            # try front page scrape as fallback
            got = fetch_site_front_page(u)
        pool.extend(got)

    # Dedupe by URL, keep first occurrence
    seen = set()
    uniq: List[Dict[str, str]] = []
    for it in pool:
        url = it["url"]
        if url in seen:
            continue
        seen.add(url)
        uniq.append(it)

    # Light sort: prefer Purdue-first sources and keep recent-ish order from feeds
    def bias(it: Dict[str, str]) -> int:
        s = (it.get("source") or "").lower()
        if "purduesports" in s: return 3
        if "hammer" in s:       return 2
        if "gold and black" in s: return 2
        if "247" in s or "rivals" in s: return 1
        return 0
    uniq.sort(key=lambda x: bias(x), reverse=True)

    # Trim
    return uniq[:12]

# ---------------------------------------------------------------------
# SCHEDULE (unchanged robust collector)
# ---------------------------------------------------------------------

def normalize_game(
    when_utc: Optional[datetime],
    opponent: str,
    site: str,
    venue: Optional[str],
    city_state: Optional[str],
    label: Optional[str],
    link: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not opponent:
        return None
    if when_utc is None or when_utc < now_utc():
        return None
    return {
        "date_iso": to_iso(when_utc),
        "date_local": human_local(when_utc),
        "opponent": opponent,
        "site": site,  # Home | Away | Neutral
        "venue": venue or "",
        "city_state": city_state or "",
        "event": label or "",
        "link": link or "",
    }

def fetch_purduesports_schedule() -> List[Dict[str, Any]]:
    print(f"[schedule] PurdueSports: {PURDUE_SCHEDULE_URL}")
    r = requests.get(PURDUE_SCHEDULE_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    games: List[Dict[str, Any]] = []
    rows = soup.select("[role='row'], article, .schedule__event, .sidearm-schedule-event")
    if not rows:
        print("[schedule] PurdueSports: structure unrecognized")
        return games

    for row in rows:
        try:
            text = " ".join(row.get_text(" ", strip=True).split())
            if not text:
                continue

            # opponent
            opp = ""
            m_opp = re.search(r"\b(?:vs\.?|at)\s+([A-Za-z0-9\-\.'& ]+)", text, re.I)
            if m_opp:
                opp = m_opp.group(1).strip()
            else:
                m2 = re.search(r"\b(?:against|vs|vs\.|at)\b\s*([A-Za-z0-9\-\.'& ]+)", text, re.I)
                if m2:
                    opp = m2.group(1).strip()

            # site
            site = "Home"
            if re.search(r"\bat\b", text, re.I):
                site = "Away"
            if re.search(r"\bneutral\b", text, re.I):
                site = "Neutral"

            # datetime
            m_dt = re.search(r"([A-Za-z]{3,9},?\s+[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{1,2}:\d{2}\s*[AP]M)", text, re.I)
            when = safe_parse_datetime(m_dt.group(1)) if m_dt else None
            if not when:
                m_d = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})", text)
                if m_d:
                    when = safe_parse_datetime(m_d.group(1))

            # venue & city
            venue = None
            city_state = None
            m_loc = re.search(r"Location:\s*([^|]+?)(?:\s*[-–—]\s*(.*))?$", text, re.I)
            if m_loc:
                venue = m_loc.group(1).strip()
                if len(m_loc.groups()) > 1 and m_loc.group(2):
                    city_state = m_loc.group(2).strip()

            label = "Exhibition" if re.search(r"Exhibition", text, re.I) else None

            link = None
            a = row.find("a", href=True)
            if a and a["href"].startswith("http"):
                link = a["href"]

            g = normalize_game(when, opp, site, venue, city_state, label, link)
            if g:
                games.append(g)

        except Exception as e:
            print(f"[schedule] PurdueSports row parse error: {e}", file=sys.stderr)

    # dedupe by (date, opponent)
    seen = set(); uniq: List[Dict[str, Any]] = []
    for g in games:
        key = (g["date_iso"], g["opponent"])
        if key in seen: continue
        seen.add(key); uniq.append(g)
    print(f"[schedule] PurdueSports parsed {len(uniq)} upcoming")
    return uniq

def fetch_espn_schedule() -> List[Dict[str, Any]]:
    print(f"[schedule] ESPN: {ESPN_SCHEDULE_URL}")
    r = requests.get(ESPN_SCHEDULE_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    events = data.get("events", []) or []
    games: List[Dict[str, Any]] = []

    for ev in events:
        try:
            comp = (ev.get("competitions") or [{}])[0]
            date_iso_raw = ev.get("date") or comp.get("date")
            when = safe_parse_datetime(date_iso_raw)

            competitors = (comp.get("competitors") or [])
            opponent, site = "", "Home"
            for c in competitors:
                team = (c.get("team") or {})
                name = team.get("displayName") or team.get("shortDisplayName") or ""
                ha = (c.get("homeAway") or "").lower()
                if "purdue" not in (name.lower()):
                    opponent = name
                if ha == "away" and "purdue" in name.lower():
                    site = "Away"
                if ha == "home" and "purdue" in name.lower():
                    site = "Home"

            venue_name, city_state = "", ""
            venue = comp.get("venue") or {}
            v_full = venue.get("fullName")
            if v_full: venue_name = v_full
            address = venue.get("address") or {}
            city = address.get("city"); state = address.get("state")
            if city or state:
                city_state = ", ".join([s for s in [city, state] if s])

            label = "Exhibition" if "exhibition" in (ev.get("name") or "").lower() else None

            link = None
            links = (ev.get("links") or []) + (comp.get("links") or [])
            for l in links:
                if l.get("href"):
                    link = l["href"]; break

            g = normalize_game(when, opponent, site, venue_name, city_state, label, link)
            if g:
                games.append(g)

        except Exception as e:
            print(f"[schedule] ESPN event parse error: {e}", file=sys.stderr)

    # dedupe
    seen = set(); uniq: List[Dict[str, Any]] = []
    for g in games:
        key = (g["date_iso"], g["opponent"])
        if key in seen: continue
        seen.add(key); uniq.append(g)
    uniq.sort(key=lambda x: x["date_iso"])
    print(f"[schedule] ESPN parsed {len(uniq)} upcoming")
    return uniq

def collect_schedule_payload() -> Dict[str, Any]:
    try:
        ps = fetch_purduesports_schedule()
    except Exception as e:
        print(f"[schedule] PurdueSports fetch failed: {e}", file=sys.stderr)
        ps = []
    try:
        es = fetch_espn_schedule()
    except Exception as e:
        print(f"[schedule] ESPN fetch failed: {e}", file=sys.stderr)
        es = []

    combined: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for g in es:
        combined[(g["date_iso"], g["opponent"])] = g
    for g in ps:
        combined[(g["date_iso"], g["opponent"])] = g  # official overrides

    games = list(combined.values())
    games.sort(key=lambda g: g["date_iso"])

    if not games:
        prev = read_json(OUT_SCHEDULE, None)
        if prev and isinstance(prev.get("games"), list) and prev["games"]:
            games = prev["games"]
            source = prev.get("source", "previous")
        else:
            source = "empty"
    else:
        source = "purduesports+espn" if (ps and es) else ("purduesports" if ps else "espn")

    return {
        "team": TEAM_NAME,
        "updated_at": to_iso(now_utc()),
        "source": source,
        "games": games,
    }

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    # BEAT LINKS (expanded)
    beats_last = read_json(OUT_BEATS, [])
    try:
        beats = collect_beats()
        if not beats:
            beats = beats_last
        # write as ARRAY the UI expects
        write_json(OUT_BEATS, beats)
        print(f"[beats] wrote {OUT_BEATS} ({len(beats)} items)")
    except Exception as e:
        print(f"[beats] fatal: {e}", file=sys.stderr)
        if beats_last:
            write_json(OUT_BEATS, beats_last)

    # SCHEDULE (unchanged robust behavior)
    sched_last = read_json(OUT_SCHEDULE, None)
    try:
        payload = collect_schedule_payload()
        write_json(OUT_SCHEDULE, payload)
        print(f"[schedule] wrote {OUT_SCHEDULE} ({len(payload['games'])} games, source={payload['source']})")
    except Exception as e:
        print(f"[schedule] fatal: {e}", file=sys.stderr)
        if sched_last:
            write_json(OUT_SCHEDULE, sched_last)

if __name__ == "__main__":
    main()