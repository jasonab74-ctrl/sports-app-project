#!/usr/bin/env python3
# tools/schedule_collect.py
#
# Builds static/teams/purdue-mbb/schedule.json by:
#  1) Parsing the official ICS feed (reliable times in UTC)
#  2) Scraping the Purdue schedule page for richer labels (opponent, tv, event, city)
#  3) Merging BOTH sources and also ADDING page-only games missing from ICS (exhibitions/charity)
#  4) Applying manual overrides (schedule_overrides.json), including ability to ADD games
#  5) (Optional) Adding odds from The Odds API when ODDS_API_KEY is set
#
# Logs are plain text; ends with:
#   "Wrote .../schedule.json with N games."
#   "Odds updated for K games."

import os, json, re, datetime
from datetime import timezone
from urllib.parse import urljoin
import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    os.system("pip install beautifulsoup4 >/dev/null 2>&1")
    from bs4 import BeautifulSoup  # type: ignore

try:
    import zoneinfo  # Py3.9+
except Exception:
    zoneinfo = None

ROOT = os.path.dirname(os.path.dirname(__file__))
TEAM_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
CFG_PATH = os.path.join(TEAM_DIR, "config.json")
OVR_PATH = os.path.join(TEAM_DIR, "schedule_overrides.json")
OUT_PATH = os.path.join(TEAM_DIR, "schedule.json")

HOME_TZ = "America/Indiana/Indianapolis"  # West Lafayette (ET)
FALLBACK_TZ = "America/New_York"          # Safe default for many away/neutral eastern events

# ---------- helpers ----------
def load_json(path, default=None):
    if not os.path.exists(path): return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def to_utc_iso(local_dt: datetime.datetime, tz_name: str) -> str:
    if zoneinfo is None:
        # last-ditch: assume input already UTC-ish
        return local_dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo(FALLBACK_TZ)
    return local_dt.replace(tzinfo=tz).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

# ---------- ICS ----------
def parse_ics(ics_text):
    events, block = [], []
    for line in ics_text.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            block = []
        if line:
            block.append(line)
        if line == "END:VEVENT":
            events.append(block)
            block = []

    items = []
    for b in events:
        rec = {}
        for l in b:
            if l.startswith("DTSTART"):
                m = re.search(r":(\d{8}T\d{6}Z?)$", l)
                if m:
                    raw = m.group(1)
                    if raw.endswith("Z"):
                        dt = datetime.datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                    else:
                        # If timezone not provided, treat as HOME_TZ
                        local = datetime.datetime.strptime(raw, "%Y%m%dT%H%M%S")
                        if zoneinfo:
                            dt = local.replace(tzinfo=zoneinfo.ZoneInfo(HOME_TZ)).astimezone(timezone.utc)
                        else:
                            dt = local.replace(tzinfo=timezone.utc)
                    rec["utc"] = dt.isoformat().replace("+00:00", "Z")
            elif l.startswith("SUMMARY:"):
                rec["summary"] = l.split("SUMMARY:", 1)[1].strip()
            elif l.startswith("LOCATION:"):
                rec["location"] = l.split("LOCATION:", 1)[1].strip()
            elif l.startswith("DESCRIPTION:"):
                rec["description"] = l.split("DESCRIPTION:", 1)[1].strip()
        if "utc" in rec:
            items.append(rec)
    return items

def classify_venue(summary, location, desc):
    text = " ".join(filter(None, [summary, location, desc])).lower()
    if any(k in text for k in ("home", "mackey")): return "Home"
    if "away" in text: return "Away"
    s = (summary or "").lower()
    if " vs " in s: return "Home"
    if " at " in s: return "Away"
    return "Neutral"

def clean_opponent(summary):
    if not summary:
        return "TBD"
    s = summary
    s = re.sub(r"^[A-Za-z0-9&'().\-: ]*?:\s*", "", s)  # strip event prefixes
    m = re.search(r"\b(?:vs|vs\.|v\.|v|versus)\b\s+(.*)$", s, flags=re.I)
    if not m:
        m = re.search(r"\b(?:at|@)\b\s+(.*)$", s, flags=re.I)
    opp = (m.group(1).strip() if m else s)
    opp = re.sub(r"\bPurdue\b.*", "", opp, flags=re.I)
    opp = re.sub(r"\s*\(.*?\)$", "", opp).strip("-–—: ").strip()
    return opp or "TBD"

# ---------- Page scrape (Sidearm variants) ----------
TIME_RX = re.compile(r'(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>AM|PM)\s*(?P<tz>[A-Z]{2,4})?', re.I)

def parse_local_time(text: str):
    """Return (hour, minute, tz_name or None) if we can parse a time like '6 PM ET' or '7:30 PM'."""
    m = TIME_RX.search(text or "")
    if not m: return None, None, None
    h = int(m.group("h"))
    mnt = int(m.group("m") or 0)
    ampm = (m.group("ampm") or "").upper()
    tz_abbr = (m.group("tz") or "").upper()
    if ampm == "PM" and h != 12: h += 12
    if ampm == "AM" and h == 12: h = 0
    tz_name = None
    if tz_abbr in ("ET","EDT","EST"): tz_name = "America/New_York"
    if tz_abbr in ("CT","CDT","CST"): tz_name = "America/Chicago"
    return h, mnt, tz_name

def scrape_schedule_page(url):
    """Scrape the schedule page to collect richer fields AND local date/time/venue when available."""
    try:
        html = fetch(url)
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")

    games = []
    # Generic selectors across Sidearm versions
    rows = soup.select(".sidearm-schedule-game, .schedule__list-item, li[data-game-date], .schedule-game")
    for row in rows:
        # Date (ISO if available)
        date_iso = row.get("data-game-date", "").strip()
        date_text = ""
        time_text = ""

        # Try to find explicit time tag first
        t_tag = row.select_one("time[datetime]")
        if t_tag and t_tag.has_attr("datetime"):
            date_iso = t_tag["datetime"].strip()
        if not date_iso:
            # fallback textual date/time lumps
            dt_el = row.select_one(".date, .game-date, .sidearm-schedule-game-opponent-date")
            if dt_el: 
                date_text = dt_el.get_text(" ", strip=True)

        # Opponent
        opp_el = row.select_one(".sidearm-schedule-game-opponent-name, .opponent, .opponent-name, .sidearm-schedule-game-opponent-text, .game-opponent")
        opponent = (opp_el.get_text(" ", strip=True) if opp_el else "")
        opponent = opponent.replace("vs", "").replace("at", "").strip(" -–—:|")

        # Event/tournament
        ev_el = row.select_one(".sidearm-schedule-game-opponent-title, .event, .game-title, .game__title")
        event = ev_el.get_text(" ", strip=True) if ev_el else ""

        # TV / Network
        tv_el = row.select_one(".sidearm-schedule-game-coverage, .tv, .network, .game-tv")
        tv = tv_el.get_text(" ", strip=True).replace("TV:", "").strip() if tv_el else ""

        # Location
        loc_el = row.select_one(".sidearm-schedule-game-location, .location, .game-location")
        location = loc_el.get_text(" ", strip=True) if loc_el else ""

        # Find any standalone time text in row (fallback)
        if not t_tag:
            txt_sample = row.get_text(" ", strip=True)
            mh, mm, tz_name = parse_local_time(txt_sample)
        else:
            mh = mm = tz_name = None

        # Link
        link_el = row.select_one("a[href*='/schedule/'], a[href*='/sports/']")
        url_abs = urljoin(url, link_el["href"]) if link_el and link_el.has_attr("href") else ""

        games.append({
            "opponent": opponent or "TBD",
            "local_date_iso_or_text": date_iso or date_text,
            "parsed_h": mh, "parsed_m": mm, "parsed_tz": tz_name,
            "location_text": location,
            "event": event,
            "tv": tv,
            "url": url_abs
        })
    return games

def build_page_only_game(pg) -> dict | None:
    """Construct a UTC datetime if ICS doesn't have this game."""
    src = pg.get("local_date_iso_or_text","")
    if not src:
        return None

    # 1) Try ISO from <time datetime="...">
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", src):
            # Sidearm usually uses local datetime in ISO; treat as HOME_TZ unless tz parsed
            date_only = src[:10]
            # If <time datetime> includes time, use it; else fallback to parsed_h/m or 19:00
            if "T" in src:
                # Assume already local; attach tz and convert
                dt_parts = src.replace("Z","").split("T")
                y,m,d = map(int, dt_parts[0].split("-"))
                hh,mm = (19,0)
                if len(dt_parts) > 1 and re.match(r"^\d{2}:\d{2}", dt_parts[1]):
                    hh,mm = map(int, dt_parts[1][:5].split(":"))
                tz_name = pg.get("parsed_tz") or HOME_TZ
                local_dt = datetime.datetime(y,m,d,hh,mm,0)
                utc = to_utc_iso(local_dt, tz_name)
                return {"utc": utc}
            else:
                y,m,d = map(int, date_only.split("-"))
                hh = pg.get("parsed_h") if pg.get("parsed_h") is not None else 19
                mm = pg.get("parsed_m") if pg.get("parsed_m") is not None else 0
                tz_name = pg.get("parsed_tz") or HOME_TZ
                local_dt = datetime.datetime(y,m,d,hh,mm,0)
                utc = to_utc_iso(local_dt, tz_name)
                return {"utc": utc}
    except Exception:
        pass

    # 2) Last resort: try loose "Oct 24, 6 PM ET" text in src
    try:
        mdate = re.search(r'(?P<mon>[A-Za-z]{3,9})\.?\s*(?P<day>\d{1,2})', src)
        if mdate:
            mon = mdate.group("mon")[:3].title()
            month_map = {k:i for i,k in enumerate(
                ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1)}
            y = datetime.datetime.now().year
            m = month_map.get(mon, 11)
            d = int(mdate.group("day"))
            hh = pg.get("parsed_h") if pg.get("parsed_h") is not None else 19
            mm = pg.get("parsed_m") if pg.get("parsed_m") is not None else 0
            tz_name = pg.get("parsed_tz") or HOME_TZ
            local_dt = datetime.datetime(y, m, d, hh, mm, 0)
            utc = to_utc_iso(local_dt, tz_name)
            return {"utc": utc}
    except Exception:
        pass

    return None

# ---------- Overrides ----------
def infer_local_date_str(iso_utc):
    dt = datetime.datetime.fromisoformat(iso_utc.replace("Z","+00:00"))
    local = dt.astimezone()
    return local.strftime("%Y-%m-%d")

def apply_overrides_update(games, overrides):
    """Update fields for games that already exist (matched by local date)."""
    if not overrides or not overrides.get("games"): return games
    by_date = {}
    for g in games:
        by_date.setdefault(infer_local_date_str(g["utc"]), []).append(g)

    for o in overrides["games"]:
        date = o.get("date")
        if not date: continue
        if date in by_date:
            for g in by_date[date]:
                for k in ("opponent","venue","location","event","tv","url"):
                    if o.get(k): g[k] = o[k]
    return games

def apply_overrides_add(games, overrides):
    """Add new games explicitly from overrides.add (must include 'utc')."""
    if not overrides or not overrides.get("add"): return games
    have = {(g["utc"], g["opponent"]) for g in games}
    for a in overrides["add"]:
        utc = a.get("utc")
        opp = a.get("opponent","TBD")
        if not utc: continue
        key = (utc, opp)
        if key in have: continue
        games.append({
            "opponent": opp,
            "utc": utc,
            "venue": a.get("venue","Neutral"),
            "location": a.get("location",""),
            "event": a.get("event",""),
            "tv": a.get("tv",""),
            "url": a.get("url","")
        })
    return games

# ---------- Odds ----------
def add_odds(cfg, games):
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        return games, 0
    updated = 0
    base = f"https://api.the-odds-api.com/v4/sports/{cfg['sport_key']}/odds"
    for g in games:
        try:
            dt = datetime.datetime.fromisoformat(g["utc"].replace("Z","+00:00"))
            from_iso = (dt - datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            to_iso   = (dt + datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            params = {
                "regions": "us",
                "markets": "h2h,spreads,totals",
                "bookmakers": ",".join(cfg.get("books",[])),
                "dateFormat": "iso",
                "oddsFormat": "american",
                "apiKey": api_key,
                "commenceTimeFrom": from_iso,
                "commenceTimeTo": to_iso,
            }
            r = requests.get(base, params=params, timeout=25)
            if r.status_code != 200: continue
            payload = r.json()

            def norm(s): return re.sub(r"[^a-z0-9]+","", (s or "").lower())
            n_team = norm(cfg["team_name"]); n_opp  = norm(g.get("opponent",""))

            match = None
            for item in payload:
                teams = item.get("participants") or item.get("teams") or []
                teams = [norm(t) for t in teams] or [norm(item.get("home_team","")), norm(item.get("away_team",""))]
                if n_team in teams and n_opp in teams:
                    match = item; break
            if not match: continue

            snaps = []
            for bk in match.get("bookmakers", []):
                name = bk.get("key")
                mkts = {m["key"]: m for m in bk.get("markets", [])}
                spread = total = money = None
                if mkts.get("spreads") and mkts["spreads"].get("outcomes"):
                    for o in mkts["spreads"]["outcomes"]:
                        if norm(o.get("name")) == n_team:
                            spread = o.get("point"); break
                if mkts.get("totals") and mkts["totals"].get("outcomes"):
                    outs = mkts["totals"]["outcomes"]
                    if outs: total = outs[0].get("point")
                if mkts.get("h2h") and mkts["h2h"].get("outcomes"):
                    for o in mkts["h2h"]["outcomes"]:
                        if norm(o.get("name")) == n_team:
                            money = o.get("price"); break
                if any(v is not None for v in (spread, total, money)):
                    snaps.append({"book": name, "spread": spread, "total": total, "moneyline": money})
            if snaps:
                g["odds"] = {
                    "source": "the-odds-api",
                    "consensus": snaps,
                    "updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
                }
                updated += 1
        except Exception:
            continue
    return games, updated

# ---------- main ----------
def main():
    cfg = load_json(CFG_PATH, {})
    if not cfg:
        raise SystemExit("Missing config.json in team directory")

    print("Fetching ICS...")
    ics_items = []
    try:
        ics_text = fetch(cfg["ics_url"])
        ics_items = parse_ics(ics_text)
    except Exception as e:
        print(f"ICS fetch/parse failed: {e}")

    print(f"Parsed {len(ics_items)} ICS events.")

    # index ICS by UTC date for matching
    by_day = {}
    for it in ics_items:
        day = it["utc"].split("T")[0]
        by_day.setdefault(day, []).append(it)

    print("Scraping schedule page for labels + page-only games...")
    page_games = []
    try:
        page_games = scrape_schedule_page(cfg["schedule_url"])
    except Exception as e:
        print(f"Schedule page scrape failed: {e}")
    print(f"Found {len(page_games)} rows on schedule page.")

    merged = []

    # 1) For every ICS event, enrich from page if possible
    for day, games in sorted(by_day.items(), key=lambda kv: kv[0]):
        for it in games:
            summary = it.get("summary",""); desc = it.get("description",""); loc_raw = it.get("location","")
            opponent = clean_opponent(summary)
            venue = classify_venue(summary, loc_raw, desc)
            event = tv = url = location = ""

            # try to find a page row for same calendar day (local), else leave empty
            page_match = None
            if page_games:
                try:
                    utc_dt = datetime.datetime.fromisoformat(it["utc"].replace("Z","+00:00")).astimezone()
                    day_local = utc_dt.strftime("%Y-%m-%d")
                    for pg in page_games:
                        src = pg.get("local_date_iso_or_text","")
                        if day_local and day_local in src:
                            page_match = pg; break
                except Exception:
                    pass

            if page_match:
                if page_match.get("opponent"): opponent = page_match["opponent"] or opponent
                if page_match.get("event"): event = page_match["event"]
                if page_match.get("tv"): tv = page_match["tv"]
                if page_match.get("url"): url = page_match["url"]
                if page_match.get("location_text"): location = page_match["location_text"]
            else:
                location = loc_raw

            merged.append({
                "opponent": opponent or "TBD",
                "utc": it["utc"],
                "venue": venue,
                "location": location,
                "event": event,
                "tv": tv,
                "url": url
            })

    # 2) Add page-only games that are not in ICS (e.g., exhibitions)
    # Build a set of UTC days already present from ICS
    have_days = {g["utc"].split("T")[0] for g in merged}
    added_page_only = 0
    for pg in page_games:
        # If page has a date that isn't in ICS, build a UTC and add it
        src = pg.get("local_date_iso_or_text","")
        if not src: continue

        # Determine local date components
        y=m=d=None
        if re.match(r"^\d{4}-\d{2}-\d{2}", src):
            y,m,d = map(int, src[:10].split("-"))
        else:
            # soft parse like "Oct 24"
            mdate = re.search(r'(?P<mon>[A-Za-z]{3,9})\.?\s*(?P<day>\d{1,2})', src)
            if mdate:
                mon = mdate.group("mon")[:3].title()
                month_map = {k:i for i,k in enumerate(
                    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1)}
                y = datetime.datetime.now().year
                m = month_map.get(mon)
                d = int(mdate.group("day"))
        if not (y and m and d): continue
        day_key = f"{y:04d}-{m:02d}-{d:02d}"
        if day_key in have_days:
            continue  # already covered by ICS

        # Build local time (fallback 7:00 PM if missing)
        hh = pg.get("parsed_h") if pg.get("parsed_h") is not None else 19
        mm = pg.get("parsed_m") if pg.get("parsed_m") is not None else 0
        tz_name = pg.get("parsed_tz") or HOME_TZ
        local_dt = datetime.datetime(y,m,d,hh,mm,0)
        utc = to_utc_iso(local_dt, tz_name)

        merged.append({
            "opponent": (pg.get("opponent") or "TBD"),
            "utc": utc,
            "venue": "Away" if "at " in (pg.get("opponent","").lower()) else "Neutral",  # coarse guess; can be overridden
            "location": pg.get("location_text",""),
            "event": pg.get("event",""),
            "tv": pg.get("tv",""),
            "url": pg.get("url","")
        })
        have_days.add(day_key)
        added_page_only += 1

    # 3) Manual overrides
    overrides = load_json(OVR_PATH, {})
    merged = apply_overrides_update(merged, overrides)  # update existing
    merged = apply_overrides_add(merged, overrides)     # add explicit games (requires utc)

    # 4) Odds (optional)
    merged.sort(key=lambda x: x["utc"])
    merged, n_with_odds = add_odds(cfg, merged)

    out = {
        "updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "games": merged
    }
    save_json(OUT_PATH, out)

    print(f"Wrote {OUT_PATH} with {len(merged)} games.")
    print(f"Odds updated for {n_with_odds} games.")
    if added_page_only:
        print(f"Added {added_page_only} page-only games (exhibitions/charity).")

if __name__ == "__main__":
    main()
