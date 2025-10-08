#!/usr/bin/env python3
# tools/roster_collect.py
#
# Scrape Purdue's official roster (Sidearm) and output:
#   static/teams/purdue-mbb/roster.json
#
# Fields: num, name, pos, height, weight, year, hometown (if present)

import os, json, re, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(__file__))
TEAM_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
CFG_PATH = os.path.join(TEAM_DIR, "config.json")
OUT_PATH = os.path.join(TEAM_DIR, "roster.json")

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

def clean(s): return re.sub(r"\s+", " ", (s or "").strip())
def parse_weight(s):
    m = re.search(r"(\d+)\s*lbs?", s or "", re.I)
    return int(m.group(1)) if m else None
def parse_height(s):
    s = (s or "").replace("’","'").replace("″",'"')
    m = re.search(r"(\d)\s*[-']\s*(\d{1,2})", s)
    if m: return f"{m.group(1)}-{m.group(2)}"
    return s.strip() or None

def scrape_sidearm_roster(url):
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    players = []

    cards = soup.select(".sidearm-roster-player, .sidearm-roster-players__item, .roster__player, li[data-player-id]")
    if not cards:
        rows = soup.select("table.sidearm-table tbody tr")
        for tr in rows:
            tds = [clean(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if len(tds) < 5: continue
            num = re.sub(r"[^\d]", "", tds[0]) or None
            name = tds[1]
            pos = tds[2]
            height = parse_height(tds[3])
            weight = parse_weight(tds[4])
            year = tds[5] if len(tds) > 5 else ""
            players.append({"num": num, "name": name, "pos": pos, "height": height, "weight": weight, "year": year})
        return players

    for c in cards:
        num = None; name=""; pos=""; height=None; weight=None; year=""; home=""
        n_el = c.select_one(".sidearm-roster-player-jersey-number, .roster__jersey, .number")
        if n_el:
            m = re.search(r"\d+", n_el.get_text())
            if m: num = m.group(0)
        nm = c.select_one(".sidearm-roster-player-name, .name, a[href*='/roster/']")
        name = clean(nm.get_text()) if nm else ""
        p_el = c.select_one(".sidearm-roster-player-position, .position, .pos")
        pos = clean(p_el.get_text()) if p_el else ""
        meta_text = c.get_text(" ", strip=True)
        height = parse_height(meta_text)
        weight = parse_weight(meta_text)
        y_el = c.select_one(".sidearm-roster-player-academic-year, .academic-year, .year")
        year = clean(y_el.get_text()) if y_el else year
        home_el = c.select_one(".sidearm-roster-player-hometown, .hometown")
        home = clean(home_el.get_text()) if home_el else ""

        players.append({
            "num": num, "name": name, "pos": pos, "height": height,
            "weight": weight, "year": year, "hometown": home
        })
    return players

def main():
    cfg = load_json(CFG_PATH, {})
    if not cfg or not cfg.get("roster_url"):
        raise SystemExit("Missing roster_url in config.json")
    print("Scraping roster…")
    players = scrape_sidearm_roster(cfg["roster_url"])
    print(f"Found {len(players)} players.")
    out = {
        "updated": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "players": players
    }
    save_json(OUT_PATH, out)
    print(f"Wrote {OUT_PATH}")

if __name__ == "__main__":
    main()