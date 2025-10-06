#!/usr/bin/env python3
# tools/schedule_collect.py
import os, json, re, requests, datetime
from datetime import timezone
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(__file__))
TEAM_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
CFG_PATH = os.path.join(TEAM_DIR, "config.json")
OUT_PATH = os.path.join(TEAM_DIR, "schedule.json")

def load_cfg():
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_ics(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def parse_ics(ics_text):
    # Minimal iCal parser for VEVENT blocks we care about
    events = []
    block = []
    for line in ics_text.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            block = []
        block.append(line)
        if line == "END:VEVENT":
            events.append(block)
            block = []

    items = []
    for b in events:
        data = {}
        for l in b:
            if l.startswith("DTSTART"):
                # Support ...;TZID=America/Chicago:20251111T190000 or UTC Z
                m = re.search(r":(\d{8}T\d{6}Z?)$", l)
                if m:
                    raw = m.group(1)
                    if raw.endswith("Z"):
                        dt = datetime.datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                    else:
                        # Treat naive as local to America/Chicago (typical Purdue home), convert to UTC
                        local = datetime.datetime.strptime(raw, "%Y%m%dT%H%M%S")
                        # You can change this default tz if needed
                        try:
                            import zoneinfo
                            tz = zoneinfo.ZoneInfo("America/Chicago")
                            dt = local.replace(tzinfo=tz).astimezone(timezone.utc)
                        except Exception:
                            dt = local.replace(tzinfo=timezone.utc)
                    data["utc"] = dt.isoformat().replace("+00:00","Z")
            elif l.startswith("SUMMARY:"):
                data["summary"] = l.split("SUMMARY:",1)[1].strip()
            elif l.startswith("LOCATION:"):
                data["location"] = l.split("LOCATION:",1)[1].strip()
            elif l.startswith("DESCRIPTION:"):
                desc = l.split("DESCRIPTION:",1)[1].strip()
                data["description"] = desc
        if "utc" in data and "summary" in data:
            items.append(data)
    return items

def classify_home_away(summary, location):
    text = f"{summary} {location or ''}".lower()
    if " vs " in summary.lower() or "home" in text:
        return "Home"
    if " at " in summary.lower() or "away" in text:
        return "Away"
    return "Neutral"

def clean_opponent(summary):
    # Examples: "Purdue vs Indiana", "Purdue at Gonzaga", "PKI: Purdue vs Duke"
    s = summary
    # Strip known prefixes like events/tournaments
    s = re.sub(r"^[A-Za-z0-9&'().\-: ]*?:\s*", "", s)
    m = re.search(r"\b(?:vs|VS|Vs)\b\s+(.*)$", s)
    if not m:
        m = re.search(r"\b(?:at|AT|At)\b\s+(.*)$", s)
    if m:
        opp = m.group(1).strip()
    else:
        # Fallback: remove "Purdue" and separators
        opp = re.sub(r"\bPurdue\b", "", s, flags=re.I)
        opp = re.sub(r"[-–—:@]+", " ", opp).strip()
    # Trim trailing brackets etc.
    opp = re.sub(r"\s*\(.*?\)$", "", opp).strip()
    return opp

def fetch_odds(cfg, team_name, dt_utc, opponent):
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        return None
    # Query window around game date to catch overnight postings
    date_from = (datetime.datetime.fromisoformat(dt_utc.replace("Z","+00:00")) - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_to   = (datetime.datetime.fromisoformat(dt_utc.replace("Z","+00:00")) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "bookmakers": ",".join(cfg.get("books",[])),
        "dateFormat": "iso",
        "oddsFormat": "american",
        "apiKey": api_key,
        "commenceTimeFrom": date_from,
        "commenceTimeTo": date_to,
    }
    url = f"https://api.the-odds-api.com/v4/sports/{quote(cfg['sport_key'])}/odds"
    try:
        r = requests.get(url, params=params, timeout=25)
        if r.status_code != 200:
            return None
        games = r.json()
    except Exception:
        return None

    # very simple matcher: both team names must appear in participants (case-insensitive substring match)
    def norm(s): return re.sub(r"[^a-z0-9]+","", s.lower())
    n_team = norm(team_name)
    n_opp  = norm(opponent)

    best = None
    for g in games:
        parts = [norm(x) for x in g.get("participants") or g.get("teams") or []]
        if not parts:
            # some responses shape: home_team/away_team
            parts = [norm(g.get("home_team","")), norm(g.get("away_team",""))]
        if (n_team in parts or any(n_team in p for p in parts)) and (n_opp in parts or any(n_opp in p for p in parts)):
            # Build a compact consensus snapshot
            book_snaps = []
            for bk in g.get("bookmakers", []):
                name = bk.get("key")
                mkts = {m["key"]: m for m in bk.get("markets", [])}
                spread = None; total = None; money = None
                if "spreads" in mkts and mkts["spreads"].get("outcomes"):
                    # find line for our team
                    for o in mkts["spreads"]["outcomes"]:
                        if norm(o.get("name","")) == n_team:
                            spread = o.get("point")
                            break
                if "totals" in mkts and mkts["totals"].get("outcomes"):
                    outs = mkts["totals"]["outcomes"]
                    # totals have Over/Under; take point value
                    if outs: total = outs[0].get("point")
                if "h2h" in mkts and mkts["h2h"].get("outcomes"):
                    for o in mkts["h2h"]["outcomes"]:
                        if norm(o.get("name","")) == n_team:
                            money = o.get("price")
                            break
                book_snaps.append({
                    "book": name, "spread": spread, "total": total, "moneyline": money
                })
            best = {
                "source": "the-odds-api",
                "updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                "consensus": book_snaps
            }
            break
    return best

def main():
    cfg = load_cfg()
    ics = fetch_ics(cfg["ics_url"])
    raw_events = parse_ics(ics)

    schedule = []
    for ev in raw_events:
        dt_utc = ev["utc"]
        opp = clean_opponent(ev["summary"])
        hoa = classify_home_away(ev["summary"], ev.get("location"))
        game = {
            "opponent": opp,
            "utc": dt_utc,
            "venue": hoa,           # Home | Away | Neutral
            "location": ev.get("location") or "",
            "note": ev.get("description","")
        }
        # Odds (optional, if API key present)
        try:
            odds = fetch_odds(cfg, cfg["team_name"], dt_utc, opp)
            if odds:
                game["odds"] = odds
        except Exception:
            pass
        schedule.append(game)

    schedule.sort(key=lambda x: x["utc"])
    out = {"updated": datetime.datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
           "games": schedule}
    os.makedirs(TEAM_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH} with {len(schedule)} games")

if __name__ == "__main__":
    main()
