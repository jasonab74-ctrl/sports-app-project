#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Collects Purdue Men's Basketball schedule and writes:
  static/data/schedule.json

Source order (with graceful fallback):
  1) PurdueSports.com (HTML)
  2) ESPN team schedule API (teamId=2509)
  3) Existing file on disk (keeps last-good data so UI never goes empty)

Notes
- Produces clean, normalized JSON the front-end expects.
- Keeps only upcoming games (>= 'now' UTC).
- Includes human-friendly local time strings + ISO timestamps.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

try:
    from dateutil import parser as dateutil_parser  # better parsing
except Exception:
    dateutil_parser = None

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

TEAM_NAME = "Purdue"
SPORT = "mens-basketball"
PURDUE_SCHEDULE_URL = f"https://purduesports.com/sports/{SPORT}/schedule"
ESPN_SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/2509/schedule"

OUT_DIR = "static/data"
OUT_FILE = os.path.join(OUT_DIR, "schedule.json")

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_iso(dt: datetime) -> str:
    # ISO 8601 with timezone
    return dt.astimezone(timezone.utc).isoformat()

def safe_parse_datetime(text: str) -> Optional[datetime]:
    """
    Parse many date/time formats safely.
    Returns UTC datetime or None.
    """
    if not text:
        return None
    try:
        if dateutil_parser:
            dt = dateutil_parser.parse(text)
            # If parsed datetime is naive, assume local ET then convert to UTC
            if dt.tzinfo is None:
                # best-effort: assume US/Eastern for NCAA listings
                from datetime import timedelta
                # naive dt, treat as ET (UTC-4 or -5). We approximate using -4 (DST most of season).
                dt = dt.replace(tzinfo=timezone.utc) - timedelta(hours=4)
            return dt.astimezone(timezone.utc)
        else:
            # Minimal fallback: try YYYY-MM-DD or YYYY-MM-DD HH:MM
            m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}):(\d{2}))?", text)
            if m:
                y, mo, d = map(int, m.group(1).split("-"))
                if m.group(2):
                    hh = int(m.group(2)); mm = int(m.group(3))
                    dt = datetime(y, mo, d, hh, mm, tzinfo=timezone.utc)
                else:
                    dt = datetime(y, mo, d, 0, 0, tzinfo=timezone.utc)
                return dt
    except Exception:
        return None
    return None

def human_local(dt_utc: datetime) -> str:
    """
    Returns "MM/DD/YYYY, HH:MM AM/PM local"
    We keep it simple (local to venue is hard without per-venue tz).
    The UI already labels it 'local', which is okay for our purpose.
    """
    # present in user's local browser; but we'll format a readable value
    return dt_utc.astimezone().strftime("%-m/%-d/%Y, %-I:%M %p local")

def ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)

def write_json(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

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
    # rule: only include games from now forward
    if when_utc is None:
        return None
    if when_utc < now_utc():
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

# ---------------------------------------------------------------------
# Source 1: PurdueSports HTML scraper
# ---------------------------------------------------------------------

def fetch_purduesports_schedule() -> List[Dict[str, Any]]:
    print(f"[schedule] Fetching PurdueSports: {PURDUE_SCHEDULE_URL}")
    r = requests.get(PURDUE_SCHEDULE_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # PurdueSports uses cards/rows; keep this robust with heuristics.
    # We look for items with date, opponent, location, and optionally time
    # Common structure: <div role="row"> or <article> cards.
    games: List[Dict[str, Any]] = []

    # Find rows with potential game data
    rows = soup.select("[role='row'], article, .schedule__event, .sidearm-schedule-event")
    if not rows:
        print("[schedule] PurdueSports: no recognizable rows; structure may have changed.")
        return games

    for row in rows:
        try:
            text = " ".join(row.get_text(" ", strip=True).split())
            if not text:
                continue

            # Rough filters
            if "TBA" in text.upper() and TEAM_NAME not in text:
                # We still pass through; opponent might exist with TBA time.
                pass

            # opponent
            opp = ""
            # many pages show "vs Name" or "at Name"
            m_opp = re.search(r"\b(?:vs\.?|at)\s+([A-Za-z0-9\-\.'& ]+)", text, re.I)
            if m_opp:
                opp = m_opp.group(1).strip()
            else:
                # fallback: anything after " against " or " vs ":
                m2 = re.search(r"\b(?:against|vs|vs\.|at)\b\s*([A-Za-z0-9\-\.'& ]+)", text, re.I)
                if m2:
                    opp = m2.group(1).strip()

            # site
            site = "Home"
            if re.search(r"\bat\b", text, re.I):
                site = "Away"
            if re.search(r"\bneutral\b", text, re.I):
                site = "Neutral"

            # date + time
            # Purdue often shows "Wed, Oct 24, 6:00 PM"
            m_dt = re.search(r"([A-Za-z]{3,9},?\s+[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{1,2}:\d{2}\s*[AP]M)", text, re.I)
            when = None
            if m_dt:
                when = safe_parse_datetime(m_dt.group(1))
            else:
                # Try DATE only
                m_d = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})", text)
                if m_d:
                    when = safe_parse_datetime(m_d.group(1))

            # venue + city
            venue = None
            city_state = None
            # look for "Location:" style patterns
            m_loc = re.search(r"Location:\s*([^|]+?)(?:\s*[-–—]\s*(.*))?$", text, re.I)
            if m_loc:
                venue = m_loc.group(1).strip()
                if len(m_loc.groups()) > 1 and m_loc.group(2):
                    city_state = m_loc.group(2).strip()

            # label/event
            label = None
            if re.search(r"Exhibition", text, re.I):
                label = "Exhibition"
            elif re.search(r"Opener|Opening|Season Opener", text, re.I):
                label = "Season Opener"

            # link to game details if any anchor present
            link = None
            a = row.find("a", href=True)
            if a and a["href"].startswith("http"):
                link = a["href"]

            game = normalize_game(when, opp, site, venue, city_state, label, link)
            if game:
                games.append(game)

        except Exception as e:
            print(f"[schedule] PurdueSports row parse error: {e}")

    # de-dupe by date+opponent
    seen = set()
    uniq = []
    for g in games:
        key = (g["date_iso"], g["opponent"])
        if key not in seen:
            seen.add(key)
            uniq.append(g)
    print(f"[schedule] PurdueSports parsed {len(uniq)} upcoming games")
    return uniq

# ---------------------------------------------------------------------
# Source 2: ESPN JSON
# ---------------------------------------------------------------------

def fetch_espn_schedule() -> List[Dict[str, Any]]:
    print(f"[schedule] Fetching ESPN: {ESPN_SCHEDULE_URL}")
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
            opponent = ""
            site = "Home"

            # ESPN sets homeAway on competitors
            for c in competitors:
                team = (c.get("team") or {})
                team_name = team.get("displayName") or team.get("shortDisplayName") or ""
                ha = (c.get("homeAway") or "").lower()
                # pick the opponent (the one that is not Purdue)
                if "purdue" not in team_name.lower():
                    opponent = team_name
                if ha == "away":
                    # if Purdue is marked away, then site should be Away
                    if "purdue" in team_name.lower():
                        site = "Away"
                if ha == "home":
                    if "purdue" in team_name.lower():
                        site = "Home"

            venue_name = None
            city_state = None
            venue = comp.get("venue") or {}
            v_full = venue.get("fullName")
            venue_name = v_full if v_full else None

            address = venue.get("address") or {}
            city = address.get("city")
            state = address.get("state")
            if city or state:
                city_state = ", ".join([s for s in [city, state] if s])

            label = None
            if "exhibition" in (ev.get("name") or "").lower():
                label = "Exhibition"

            link = None
            links = (ev.get("links") or []) + (comp.get("links") or [])
            for l in links:
                if l.get("href") and l.get("text", "").lower().startswith("gamecast"):
                    link = l["href"]; break
                if l.get("href") and "game" in (l.get("rel") or []):
                    link = l["href"]; break

            game = normalize_game(when, opponent, site, venue_name, city_state, label, link)
            if game:
                games.append(game)

        except Exception as e:
            print(f"[schedule] ESPN event parse error: {e}")

    # de-dupe and sort
    seen = set()
    uniq = []
    for g in games:
        key = (g["date_iso"], g["opponent"])
        if key not in seen:
            seen.add(key)
            uniq.append(g)

    uniq.sort(key=lambda g: g["date_iso"])
    print(f"[schedule] ESPN parsed {len(uniq)} upcoming games")
    return uniq

# ---------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------

def collect_schedule() -> Dict[str, Any]:
    print("[schedule] Starting collection…")

    # 1) PurdueSports first
    try:
        ps = fetch_purduesports_schedule()
    except Exception as e:
        print(f"[schedule] PurdueSports fetch failed: {e}")
        ps = []

    # 2) ESPN fallback/additive
    try:
        es = fetch_espn_schedule()
    except Exception as e:
        print(f"[schedule] ESPN fetch failed: {e}")
        es = []

    # Merge with preference to PurdueSports rows (more official)
    combined: Dict[str, Dict[str, Any]] = {}
    for g in es:
        combined[(g["date_iso"], g["opponent"])] = g
    for g in ps:
        combined[(g["date_iso"], g["opponent"])] = g  # override ESPN if same slot

    games = list(combined.values())
    games.sort(key=lambda g: g["date_iso"])

    if not games:
        print("[schedule] No upcoming games from sources; falling back to last-good file if present.")
        prev = read_json(OUT_FILE)
        if prev and isinstance(prev.get("games"), list) and prev["games"]:
            # keep previous games (some sites hide far-future slates off-season)
            games = prev["games"]
            source = prev.get("source", "previous")
        else:
            source = "empty"
    else:
        source = "purduesports+espn" if ps and es else ("purduesports" if ps else "espn")

    payload = {
        "team": TEAM_NAME,
        "updated_at": to_iso(now_utc()),
        "source": source,
        "games": games,
    }
    return payload

def main():
    ensure_outdir()

    # Only schedule here; news/roster can be handled by your existing steps.
    try:
        schedule = collect_schedule()
        write_json(OUT_FILE, schedule)
        print(f"[schedule] Wrote {OUT_FILE} with {len(schedule['games'])} games (source={schedule['source']})")
    except Exception as e:
        print(f"[schedule] Fatal error: {e}")
        # do not exit non-zero; we want the job to continue to push other assets
        # and keep last-good schedule file around
        # If you prefer to fail: sys.exit(1)

if __name__ == "__main__":
    main()