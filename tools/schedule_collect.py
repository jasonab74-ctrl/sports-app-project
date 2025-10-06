#!/usr/bin/env python3
# tools/schedule_collect.py
#
# Builds static/teams/purdue-mbb/schedule.json by:
#  1) Parsing the official ICS feed (reliable times in UTC)
#  2) Scraping the Purdue schedule page for richer labels (opponent, tv, event, city)
#  3) Applying manual overrides (schedule_overrides.json) if present
#  4) (Optional) Adding odds from The Odds API when ODDS_API_KEY is set
#
# Logs are plain text (no emojis), and end with a summary line:
#   "Odds updated for N games."

import os, json, re, datetime
from datetime import timezone
from urllib.parse import urljoin
import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
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
    if "home" in text or "mackey" in text:
        return "Home"
    if "away" in text:
        return "Away"
    s = (summary or "").lower()
    if " vs " in s: return "Home"
    if " at " in s: return "Away"
    return "Neutral"

def clean_opponent(summary):
    if not summary:
        return "TBD"
    s = summary
    s = re.sub(r"^[A-Za-z0-9&'().\-: ]*?:\s*", "", s)
    m = re.search(r"\b(?:vs|vs\.|v\.|v|versus)\b\s+(.*)$", s, flags=re.I)
    if not m:
        m = re.search(r"\b(?:at|@)\b\s+(.*)$", s, flags=re.I)
    opp = (m.group(1).strip() if m else s)
    opp = re.sub(r"\bPurdue\b.*", "", opp, flags=re.I)
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
    # Try multiple selectors (Sidearm varies across seasons)
    for row in soup.select(".sidearm-schedule-game, .schedule__list-item, li[data-game-date]"):
        dt_text = ""
        date_attr = row.get("data-game-date")
        if date_attr:
            dt_text = date_attr
        else:
            d1 = row.select_one(".sidearm-schedule-game-opponent-date, .date, time[datetime]")
            if d1 and d1.get("datetime"):
                dt_text = d1["datetime"]
            elif d1:
                dt_text = d1.get_text(" ", strip=True)

        opp_el = row.select_one(".sidearm-schedule-game-opponent-name, .opponent, .opponent-name, .sidearm-schedule-game-opponent-text")
        opponent = opp_el.get_text(" ", strip=True) if opp_el else ""
        opponent = re.sub(r"\s+at\s+", "", opponent, flags=re.I)
        opponent = opponent.replace("vs", "").replace("at", "").strip(" -–—:|")

        tv_el = row.select_one(".sidearm-schedule-game-coverage, .tv, .network")
        tv = tv_el.get_text(" ", strip=True) if tv_el else ""
        tv = tv.replace("TV:", "").strip()

        ev_el = row.select_one(".sidearm-schedule-game-opponent-title, .event, .game-title, .game__title")
        event = ev_el.get_text(" ", strip=True) if ev_el else ""

        loc_el = row.select_one(".sidearm-schedule-game-location, .location, .game-location")
        location = loc_el.get_text(" ", strip=True) if loc_el else ""

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
    local = dt.astimezone()
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
          for g in by_date[date]:
              for k in ("opponent","venue","location","event","tv","url"):
                  if o.get(k):
                      g[k] = o[k]
    return games

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
            if r.status_code != 200:
                continue
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
            if not match:
                continue

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

def main():
    cfg = load_json(CFG_PATH, {})
    if not cfg:
        raise SystemExit("Missing config.json in team directory")

    print("Fetching ICS...")
    ics_text = fetch(cfg["ics_url"])
    ics_items = parse_ics(ics_text)
    print(f"Parsed {len(ics_items)} ICS events.")

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

    print("Scraping schedule page for labels...")
    page_games = scrape_schedule_page(cfg["schedule_url"])
    print(f"Found {len(page_games)} game rows on schedule page.")

    merged = []
    for day, games in sorted(by_day.items(), key=lambda kv: kv[0]):
        for g in games:
            page_match = None
            if page_games:
                try:
                    utc_dt = datetime.datetime.fromisoformat(g["utc"].replace("Z","+00:00")).astimezone()
                    day_local = utc_dt.strftime("%Y-%m-%d")
                    for pg in page_games:
                        if pg.get("local_datetime_raw") and day_local in pg["local_datetime_raw"]:
                            page_match = pg; break
                except Exception:
                    pass
                if not page_match:
                    page_match = page_games[0]

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

    overrides = load_json(OVR_PATH, {})
    merged = apply_overrides(merged, overrides)

    print("Adding odds (if key present)...")
    merged, n_with_odds = add_odds(cfg, merged)

    merged.sort(key=lambda x: x["utc"])
    out = {
        "updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "games": merged
    }
    save_json(OUT_PATH, out)

    # Final, clean summary lines
    print(f"Wrote {OUT_PATH} with {len(merged)} games.")
    print(f"Odds updated for {n_with_odds} games.")

if __name__ == "__main__":
    main()
