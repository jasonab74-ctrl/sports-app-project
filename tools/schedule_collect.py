#!/usr/bin/env python3
# tools/schedule_collect.py
#
# Builds static/teams/purdue-mbb/schedule.json by:
#  1) Parsing the official ICS feed (reliable times in UTC)
#  2) Scraping the Purdue schedule page for richer labels (opponent, tv, event, city)
#  3) Applying manual overrides (schedule_overrides.json) if present
#  4) (Optional) Adding odds from The Odds API when ODDS_API_KEY is set

import os, json, re, datetime
from datetime import timezone
from urllib.parse import urljoin
import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    # Install if missing in the runner
    os.system("pip install beautifulsoup4 >/dev/null 2>&1")
    from bs4 import BeautifulSoup  # type: ignore

ROOT = os.path.dirname(os.path.dirname(__file__))
TEAM_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
CFG_PATH = os.path.join(TEAM_DIR, "config.json")
OVR_PATH = os.path.join(TEAM_DIR, "schedule_overrides.json")
OUT_PATH = os.path.join(TEAM_DIR, "schedule.json")

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
                        # If timezone isn’t provided, assume America/Chicago (typical)
                        local = datetime.datetime.strptime(raw, "%Y%m%dT%H%M%S")
                        try:
                            import zoneinfo
                            dt = local.replace(tzinfo=zoneinfo.ZoneInfo("America/Chicago")).astimezone(timezone.utc)
                        except Exception:
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
    # keywords beat simple "vs/at" in summary
    if "home" in text or "mackey" in text:
        return "Home"
    if "away" in text:
        return "Away"
    # fallback by vs/at
    s = (summary or "").lower()
    if " vs " in s: return "Home"
    if " at " in s: return "Away"
    return "Neutral"

def clean_opponent(summary):
    if not summary:
        return "TBD"
    s = summary
    # Strip prefixes like events/tournaments
    s = re.sub(r"^[A-Za-z0-9&'().\-: ]*?:\s*", "", s)
    # Extract after vs/at
    m = re.search(r"\b(?:vs|vs\.|v\.|v|versus)\b\s+(.*)$", s, flags=re.I)
    if not m:
        m = re.search(r"\b(?:at|@)\b\s+(.*)$", s, flags=re.I)
    opp = (m.group(1).strip() if m else s)
    opp = re.sub(r"\bPurdue\b.*", "", opp, flags=re.I)  # if Purdue appears first
    opp = re.sub(r"\s*\(.*?\)$", "", opp).strip("-–—: ").strip()
    if not opp:
        opp = "TBD"
    return opp

def scrape_schedule_page(url):
    """Scrape Sidearm schedule page to collect richer fields."""
    try:
        html = fetch(url)
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")

    games = []
    # Sidearm structures vary; attempt multiple selectors
    for row in soup.select(".sidearm-schedule-game, .schedule__list-item, li[data-game-date]"):
        # date
        dt_text = ""
        date_attr = row.get("data-game-date")
        if date_attr:
            dt_text = date_attr  # often ISO local
        else:
            d1 = row.select_one(".sidearm-schedule-game-opponent-date, .date, time[datetime]")
            if d1 and d1.get("datetime"):
                dt_text = d1["datetime"]
            elif d1:
                dt_text = d1.get_text(" ", strip=True)
        # opponent
        opp_el = row.select_one(".sidearm-schedule-game-opponent-name, .opponent, .opponent-name, .sidearm-schedule-game-opponent-text")
        opponent = opp_el.get_text(" ", strip=True) if opp_el else ""
        opponent = re.sub(r"\s+at\s+", "", opponent, flags=re.I)
        opponent = opponent.replace("vs", "").replace("at", "").strip(" -–—:|")
        # tv/network
        tv_el = row.select_one(".sidearm-schedule-game-coverage, .tv, .network")
        tv = tv_el.get_text(" ", strip=True) if tv_el else ""
        tv = tv.replace("TV:", "").strip()
        # event/tournament
        ev_el = row.select_one(".sidearm-schedule-game-opponent-title, .event, .game-title, .game__title")
        event = ev_el.get_text(" ", strip=True) if ev_el else ""
        # location text
        loc_el = row.select_one(".sidearm-schedule-game-location, .location, .game-location")
        location = loc_el.get_text(" ", strip=True) if loc_el else ""

        # link
        link_el = row.select_one("a[href*='/schedule/'], a[href*='/sports/']")
        url_abs = urljoin(url, link_el["href"]) if link_el and link_el.has_attr("href") else ""

        games.append({
            "opponent": opponent or "TBD",
            "local_datetime_raw": dt_text,
            "location_text": location,
            "event": event,
            "tv": tv,
            "url": url_abs
        })
    return games

def infer_local_date_str(iso_utc):
    dt = datetime.datetime.fromisoformat(iso_utc.replace("Z","+00:00"))
    local = dt.astimezone()  # use system tz in runner; only used for override matching
    return local.strftime("%Y-%m-%d")

def apply_overrides(games, overrides):
    if not overrides or not overrides.get("games"): return games
    by_date = {}
    for g in games:
        by_date.setdefault(infer_local_date_str(g["utc"]), []).append(g)

    for o in overrides["games"]:
        date = o.get("date")
        if not date: continue
        if date in by_date:
            # Update all games that day (usually one)
            for g in by_date[date]:
                for k in ("opponent","venue","location","event","tv","url"):
                    if o.get(k):
                        g[k] = o[k]
    return games

def add_odds(cfg, games):
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        return games
    # The Odds API — query near each game time
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
            n_team = norm(cfg["team_name"])
            n_opp  = norm(g.get("opponent",""))

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
                snaps.append({"book": name, "spread": spread, "total": total, "moneyline": money})
            if snaps:
                g["odds"] = {"source": "the-odds-api", "consensus": snaps, "updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
        except Exception:
            continue
    return games

def main():
    cfg = load_json(CFG_PATH, {})
    if not cfg: raise SystemExit("Missing config.json")

    # 1) ICS
    ics_text = fetch(cfg["ics_url"])
    ics_items = parse_ics(ics_text)

    # Map by date (UTC-day) to merge with page results
    by_day = {}
    for it in ics_items:
        utc = it["utc"]
        day = utc.split("T")[0]
        by_day.setdefault(day, []).append({
            "utc": utc,
            "summary": it.get("summary",""),
            "location_raw": it.get("location",""),
            "description": it.get("description","")
        })

    # 2) Schedule page scrape (richer labels)
    page_games = scrape_schedule_page(cfg["schedule_url"])

    # Build merged list: prefer ICS times, enrich from page where dates match
    merged = []
    for day, games in sorted(by_day.items(), key=lambda kv: kv[0]):
        for g in games:
            # find the closest matching opponent for that day (if any)
            page_match = None
            if page_games:
                # very soft match: same calendar day in runner local, or first available
                try:
                    utc_dt = datetime.datetime.fromisoformat(g["utc"].replace("Z","+00:00")).astimezone()
                    day_local = utc_dt.strftime("%Y-%m-%d")
                    for pg in page_games:
                        # if the page published a local date string, prefer match
                        if pg.get("local_datetime_raw") and day_local in pg["local_datetime_raw"]:
                            page_match = pg; break
                except Exception:
                    pass
                if not page_match:
                    page_match = page_games[0]  # fallback if page didn’t expose dates cleanly

            summary = g.get("summary","")
            desc = g.get("description","")
            loc_raw = g.get("location_raw","")

            opponent = clean_opponent(summary)
            venue = classify_venue(summary, loc_raw, desc)
            event = ""
            tv = ""
            url = ""
            location = loc_raw

            if page_match:
                if page_match.get("opponent"): opponent = page_match["opponent"] or opponent
                if page_match.get("event"): event = page_match["event"]
                if page_match.get("tv"): tv = page_match["tv"]
                if page_match.get("url"): url = page_match["url"]
                # prefer readable location from page
                if page_match.get("location_text"): location = page_match["location_text"]

            merged.append({
                "opponent": opponent or "TBD",
                "utc": g["utc"],
                "venue": venue,
                "location": location,
                "event": event,
                "tv": tv,
                "url": url
            })

    # 3) Manual overrides (optional)
    overrides = load_json(OVR_PATH, {})
    merged = apply_overrides(merged, overrides)

    # 4) Odds (optional)
    merged = add_odds(cfg, merged)

    # 5) Output
    merged.sort(key=lambda x: x["utc"])
    out = {
        "updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "games": merged
    }
    save_json(OUT_PATH, out)
    print(f"✓ Wrote {OUT_PATH} with {len(merged)} games")

if __name__ == "__main__":
    main()
