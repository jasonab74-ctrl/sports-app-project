#!/usr/bin/env python3
# tools/schedule_collect.py
#
# Output: static/teams/purdue-mbb/schedule.json
#
# Merge priority:
#  1) ESPN schedule JSON (complete, often earliest)
#  2) Purdue schedule page (Sidearm) for richer labels
#  3) Official ICS (authoritative times when present)
#  4) Manual overrides (update + add)
#  5) Odds (if ODDS_API_KEY set)
#
# Notes:
# - We key games primarily by tipoff date (UTC day) + opponent fuzzy name.
# - All times emitted as UTC ISO; UI renders local time.
# - Plain, minimal logs so your Actions don’t spam.

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
    import zoneinfo
except Exception:
    zoneinfo = None

ROOT = os.path.dirname(os.path.dirname(__file__))
TEAM_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
CFG_PATH = os.path.join(TEAM_DIR, "config.json")
OVR_PATH = os.path.join(TEAM_DIR, "schedule_overrides.json")
OUT_PATH = os.path.join(TEAM_DIR, "schedule.json")

HOME_TZ = "America/Indiana/Indianapolis"
FALLBACK_TZ = "America/New_York"

# ---------------- utils ----------------
def load_json(path, default=None):
    if not os.path.exists(path): return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch(url, params=None):
    r = requests.get(url, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.text

def to_utc_iso(local_dt: datetime.datetime, tz_name: str) -> str:
    if zoneinfo is None:
        return local_dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo(FALLBACK_TZ)
    return local_dt.replace(tzinfo=tz).astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def norm(s): return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

def pick(a, b):  # prefer a unless empty, else b
    return a if (a is not None and str(a).strip() != "") else b

# ---------------- ICS ----------------
def parse_ics(ics_text):
    events, block = [], []
    for line in ics_text.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT": block = []
        if line: block.append(line)
        if line == "END:VEVENT":
            events.append(block); block = []
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
                        local = datetime.datetime.strptime(raw, "%Y%m%dT%H%M%S")
                        if zoneinfo:
                            dt = local.replace(tzinfo=zoneinfo.ZoneInfo(HOME_TZ)).astimezone(timezone.utc)
                        else:
                            dt = local.replace(tzinfo=timezone.utc)
                    rec["utc"] = dt.isoformat().replace("+00:00","Z")
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
    if not summary: return "TBD"
    s = re.sub(r"^[A-Za-z0-9&'().\-: ]*?:\s*", "", summary)
    m = re.search(r"\b(?:vs|vs\.|v\.|v|versus)\b\s+(.*)$", s, flags=re.I)
    if not m: m = re.search(r"\b(?:at|@)\b\s+(.*)$", s, flags=re.I)
    opp = (m.group(1).strip() if m else s)
    opp = re.sub(r"\bPurdue\b.*", "", opp, flags=re.I)
    opp = re.sub(r"\s*\(.*?\)$", "", opp).strip("-–—: ").strip()
    return opp or "TBD"

# ---------------- Purdue page (Sidearm) ----------------
TIME_RX = re.compile(r'(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>AM|PM)\s*(?P<tz>[A-Z]{2,4})?', re.I)

def parse_local_time(text):
    m = TIME_RX.search(text or "")
    if not m: return None, None, None
    h = int(m.group("h")); minute = int(m.group("m") or 0)
    ampm = (m.group("ampm") or "").upper()
    tz_abbr = (m.group("tz") or "").upper()
    if ampm == "PM" and h != 12: h += 12
    if ampm == "AM" and h == 12: h = 0
    tz_name = None
    if tz_abbr in ("ET","EDT","EST"): tz_name = "America/New_York"
    if tz_abbr in ("CT","CDT","CST"): tz_name = "America/Chicago"
    return h, minute, tz_name

def scrape_sidearm(url):
    try:
        html = fetch(url)
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    games = []
    for row in soup.select(".sidearm-schedule-game, .schedule__list-item, li[data-game-date], .schedule-game"):
        date_iso = row.get("data-game-date", "").strip()
        date_text = ""
        t_tag = row.select_one("time[datetime]")
        if t_tag and t_tag.has_attr("datetime"):
            date_iso = t_tag["datetime"].strip()
        if not date_iso:
            dt_el = row.select_one(".date, .game-date, .sidearm-schedule-game-opponent-date")
            if dt_el: date_text = dt_el.get_text(" ", strip=True)

        opp_el = row.select_one(".sidearm-schedule-game-opponent-name, .opponent, .opponent-name, .sidearm-schedule-game-opponent-text, .game-opponent")
        opponent = (opp_el.get_text(" ", strip=True) if opp_el else "")
        opponent = opponent.replace("vs", "").replace("at", "").strip(" -–—:|")

        ev_el = row.select_one(".sidearm-schedule-game-opponent-title, .event, .game-title, .game__title")
        event = ev_el.get_text(" ", strip=True) if ev_el else ""

        tv_el = row.select_one(".sidearm-schedule-game-coverage, .tv, .network, .game-tv")
        tv = tv_el.get_text(" ", strip=True).replace("TV:", "").strip() if tv_el else ""

        loc_el = row.select_one(".sidearm-schedule-game-location, .location, .game-location")
        location = loc_el.get_text(" ", strip=True) if loc_el else ""

        mh=mm=tz_name=None
        if not t_tag:
            mh, mm, tz_name = parse_local_time(row.get_text(" ", strip=True))

        link_el = row.select_one("a[href*='/schedule/'], a[href*='/sports/']")
        url_abs = urljoin(url, link_el["href"]) if link_el and link_el.has_attr("href") else ""

        games.append({
            "opponent": opponent or "TBD",
            "local_date": date_iso or date_text,
            "h": mh, "m": mm, "tz": tz_name,
            "location": location,
            "event": event,
            "tv": tv,
            "url": url_abs
        })
    return games

# ---------------- ESPN JSON ----------------
def fetch_espn(team_id, seasons):
    all_games = []
    base = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{tid}/schedule"
    for yr in seasons:
        try:
            data = requests.get(base.format(tid=team_id), params={"season": yr}, timeout=30).json()
        except Exception:
            continue
        for item in (data.get("events") or []):
            try:
                date_iso = item.get("date")  # UTC ISO
                comp = (item.get("competitions") or [])[0]
                venue = "Home" if comp.get("venue",{}).get("address",{}).get("city","") and comp.get("competitors") else None
                # figure home/away via competitors
                home_team = None; away_team = None; opp_name = None; home_away = None
                for c in comp.get("competitors", []):
                    if c.get("homeAway") == "home": home_team = c
                    if c.get("homeAway") == "away": away_team = c
                # Purdue team id
                purdue_id = str(team_id)
                for c in comp.get("competitors", []):
                    if c.get("team",{}).get("id") == purdue_id:
                        home_away = c.get("homeAway")
                # opponent name
                for c in comp.get("competitors", []):
                    if c.get("team",{}).get("id") != purdue_id:
                        opp_name = c.get("team",{}).get("displayName")
                vtype = "Home" if home_away == "home" else ("Away" if home_away == "away" else "Neutral")
                city = comp.get("venue",{}).get("address",{}).get("city","")
                state = comp.get("venue",{}).get("address",{}).get("state","")
                loc = " — ".join([x for x in [comp.get("venue",{}).get("fullName",""), f"{city}, {state}".strip(", ")] if x])

                tv = ""
                tvc = comp.get("broadcasts") or []
                if tvc:
                    tv = ", ".join(sorted({b.get("names",[None])[0] for b in tvc if b.get("names")}))

                url = item.get("links",[{}])[0].get("href","")

                if date_iso and opp_name:
                    all_games.append({
                        "opponent": opp_name,
                        "utc": date_iso.replace("+00:00","Z"),
                        "venue": vtype,
                        "location": loc,
                        "event": "",
                        "tv": tv,
                        "url": url
                    })
            except Exception:
                continue
    return all_games

# ---------------- Overrides ----------------
def infer_local_date_str(iso_utc):
    dt = datetime.datetime.fromisoformat(iso_utc.replace("Z","+00:00"))
    return dt.astimezone().strftime("%Y-%m-%d")

def apply_overrides_update(games, overrides):
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
                    g[k] = pick(o.get(k), g.get(k))
    return games

def apply_overrides_add(games, overrides):
    if not overrides or not overrides.get("add"): return games
    have = {(g["utc"], norm(g["opponent"])) for g in games}
    for a in overrides["add"]:
        utc = a.get("utc"); opp = a.get("opponent","TBD")
        if not utc: continue
        key = (utc, norm(opp))
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

# ---------------- Odds ----------------
def add_odds(cfg, games):
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        return games, 0
    updated = 0
    base = f"https://api.the-odds-api.com/v4/sports/{cfg['sport_key']}/odds"
    nteam = norm(cfg["team_name"])
    for g in games:
        try:
            dt = datetime.datetime.fromisoformat(g["utc"].replace("Z","+00:00"))
            params = {
                "regions": "us",
                "markets": "h2h,spreads,totals",
                "bookmakers": ",".join(cfg.get("books",[])),
                "dateFormat": "iso",
                "oddsFormat": "american",
                "apiKey": api_key,
                "commenceTimeFrom": (dt - datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "commenceTimeTo":   (dt + datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            r = requests.get(base, params=params, timeout=25)
            if r.status_code != 200: continue
            payload = r.json()
            nopp = norm(g.get("opponent",""))
            match = None
            for item in payload:
                teams = item.get("participants") or item.get("teams") or []
                teams = [norm(t) for t in teams] or [norm(item.get("home_team","")), norm(item.get("away_team",""))]
                if nteam in teams and nopp in teams:
                    match = item; break
            if not match: continue
            snaps = []
            for bk in match.get("bookmakers", []):
                name = bk.get("key")
                mkts = {m["key"]: m for m in bk.get("markets", [])}
                spread = total = money = None
                if mkts.get("spreads") and mkts["spreads"].get("outcomes"):
                    for o in mkts["spreads"]["outcomes"]:
                        if norm(o.get("name")) == nteam:
                            spread = o.get("point"); break
                if mkts.get("totals") and mkts["totals"].get("outcomes"):
                    outs = mkts["totals"]["outcomes"]
                    if outs: total = outs[0].get("point")
                if mkts.get("h2h") and mkts["h2h"].get("outcomes"):
                    for o in mkts["h2h"]["outcomes"]:
                        if norm(o.get("name")) == nteam:
                            money = o.get("price"); break
                if any(v is not None for v in (spread,total,money)):
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

# ---------------- main ----------------
def main():
    cfg = load_json(CFG_PATH, {})
    if not cfg: raise SystemExit("Missing team config.json")

    espn_games = []
    if cfg.get("espn_team_id"):
        print("Fetching ESPN schedule…")
        espn_games = fetch_espn(cfg["espn_team_id"], cfg.get("espn_seasons", []))
    print(f"ESPN games: {len(espn_games)}")

    sidearm_games = []
    try:
        print("Scraping Purdue schedule page…")
        sidearm_games = scrape_sidearm(cfg["schedule_url"])
    except Exception as e:
        print(f"Sidearm scrape failed: {e}")
    print(f"Sidearm rows: {len(sidearm_games)}")

    ics_items = []
    try:
        print("Fetching ICS…")
        ics_text = fetch(cfg["ics_url"])
        ics_items = parse_ics(ics_text)
    except Exception as e:
        print(f"ICS failed: {e}")
    print(f"ICS events: {len(ics_items)}")

    # Indexers
    def key_from(opponent, utc):
        return (utc.split("T")[0], norm(opponent))  # day + normalized opp

    merged = {}

    # 1) seed with ESPN (best coverage)
    for g in espn_games:
        k = key_from(g["opponent"], g["utc"])
        merged[k] = {
            "opponent": g["opponent"],
            "utc": g["utc"],
            "venue": g.get("venue",""),
            "location": g.get("location",""),
            "event": g.get("event",""),
            "tv": g.get("tv",""),
            "url": g.get("url","")
        }

    # 2) enrich with Sidearm (labels, event, tv, location; may lack UTC)
    for pg in sidearm_games:
        # attempt to build a UTC from page when it doesn't match ESPN
        utc_guess = None
        src = pg.get("local_date","")
        if re.match(r"^\d{4}-\d{2}-\d{2}", src):
            y,m,d = map(int, src[:10].split("-"))
            hh = pg.get("h") if pg.get("h") is not None else 19
            mm = pg.get("m") if pg.get("m") is not None else 0
            tz_name = pg.get("tz") or HOME_TZ
            utc_guess = to_utc_iso(datetime.datetime(y,m,d,hh,mm,0), tz_name)

        # find best match by same day
        k = None
        if utc_guess:
            k = key_from(pg["opponent"], utc_guess)
            if k in merged:
                mg = merged[k]
                mg["opponent"] = pick(pg.get("opponent"), mg.get("opponent"))
                mg["location"] = pick(pg.get("location"), mg.get("location"))
                mg["event"] = pick(pg.get("event"), mg.get("event"))
                mg["tv"] = pick(pg.get("tv"), mg.get("tv"))
                mg["url"] = pick(pg.get("url"), mg.get("url"))
            else:
                merged[k] = {
                    "opponent": pg.get("opponent","TBD"),
                    "utc": utc_guess,
                    "venue": "",
                    "location": pg.get("location",""),
                    "event": pg.get("event",""),
                    "tv": pg.get("tv",""),
                    "url": pg.get("url","")
                }

    # 3) use ICS to confirm/override exact UTC time (authoritative tip)
    for it in ics_items:
        summary = it.get("summary",""); loc_raw = it.get("location",""); desc = it.get("description","")
        opp = clean_opponent(summary)
        k = key_from(opp, it["utc"])
        if k in merged:
            mg = merged[k]
            # prefer ICS utc if same day/opp but utc differs slightly
            mg["utc"] = it["utc"]
            mg["venue"] = pick(classify_venue(summary, loc_raw, desc), mg.get("venue"))
            mg["location"] = pick(mg.get("location"), loc_raw)  # keep nicer if we already have it
        else:
            merged[k] = {
                "opponent": opp,
                "utc": it["utc"],
                "venue": classify_venue(summary, loc_raw, desc),
                "location": loc_raw,
                "event": "",
                "tv": "",
                "url": ""
            }

    # 4) flatten + overrides
    out_games = list(merged.values())
    overrides = load_json(OVR_PATH, {})
    out_games = apply_overrides_update(out_games, overrides)
    out_games = apply_overrides_add(out_games, overrides)

    # 5) odds
    out_games.sort(key=lambda x: x["utc"])
    out_games, n_with_odds = add_odds(cfg, out_games)

    out = {
        "updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "games": out_games
    }
    save_json(OUT_PATH, out)
    print(f"Wrote {OUT_PATH} with {len(out_games)} games.")
    print(f"Odds updated for {n_with_odds} games.")
    print("Done.")
if __name__ == "__main__":
    main()