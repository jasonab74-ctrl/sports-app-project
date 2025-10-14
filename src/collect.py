import json, os, time
from datetime import datetime

BASE_DIR = "static"
TEAM_DIR = os.path.join(BASE_DIR, "teams", "purdue-mbb")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(TEAM_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

now_iso = datetime.utcnow().isoformat() + "Z"
now_ms = int(time.time() * 1000)

# --------- NEWS (10 items min; Purdue MBB leaning) ----------
seed_news = [
    {"title":"Purdue announces exhibition details vs. Kentucky","link":"https://purduesports.com/","image":"","ts":now_ms-10*60*1000,"source":"PurdueSports.com","tier":"official"},
    {"title":"Practice report: Guards battle for minutes at Mackey","link":"https://www.hammerandrails.com/purdue-basketball","image":"","ts":now_ms-60*60*1000,"source":"Hammer & Rails","tier":"insiders"},
    {"title":"Notebook: Mackey upgrades ahead of opener","link":"https://www.cbssports.com/college-basketball/","image":"","ts":now_ms-2*60*60*1000,"source":"CBS Sports","tier":"national"},
    {"title":"National preview: Where Purdue stacks up in Big Ten","link":"https://www.espn.com/mens-college-basketball/","image":"","ts":now_ms-3*60*60*1000,"source":"ESPN","tier":"national"},
    {"title":"Film Room: PnR counters for 2025–26","link":"https://goldandblack.com/","image":"","ts":now_ms-4*60*60*1000,"source":"Gold and Black","tier":"insiders"},
    {"title":"Braden Smith named preseason All–Big Ten","link":"https://www.yahoosports.com/college-basketball/","image":"","ts":now_ms-5*60*60*1000,"source":"Yahoo CBB","tier":"national"},
    {"title":"Roster reset: wings & rotation","link":"https://www.hammerandrails.com/purdue-basketball","image":"","ts":now_ms-6*60*60*1000,"source":"Hammer & Rails","tier":"insiders"},
    {"title":"KenPom projection hints for Purdue","link":"https://kenpom.com/","image":"","ts":now_ms-7*60*60*1000,"source":"KenPom","tier":"national"},
    {"title":"Painter on exhibitions, rotations","link":"https://purduesports.com/","image":"","ts":now_ms-8*60*60*1000,"source":"PurdueSports.com","tier":"official"},
    {"title":"Freshman spotlight: backcourt","link":"https://247sports.com/college/purdue/","image":"","ts":now_ms-9*60*60*1000,"source":"247Sports","tier":"insiders"}
]
with open(os.path.join(TEAM_DIR, "news.json"), "w") as f:
    json.dump(seed_news, f, indent=2)

# --------- SCHEDULE (upcoming) ----------
schedule = {
    "games": [
        {"opponent":"Kentucky (Exhibition)","date":"2025-10-24T15:00:00-04:00","location":"Rupp Arena — Lexington, KY","site":"Away","link":"https://purduesports.com/sports/mens-basketball/schedule"},
        {"opponent":"Evansville","date":"2025-11-04T17:00:00-05:00","location":"Mackey Arena — West Lafayette, IN","site":"Home","link":"https://purduesports.com/sports/mens-basketball/schedule"},
        {"opponent":"TBD","date":"2025-11-08T10:30:00-05:00","location":"Mackey Arena — West Lafayette, IN","site":"Home","link":"https://purduesports.com/sports/mens-basketball/schedule"},
        {"opponent":"TBD","date":"2025-11-11T18:00:00-05:00","location":"","site":"Away","link":"https://purduesports.com/sports/mens-basketball/schedule"},
        {"opponent":"TBD","date":"2025-11-18T18:00:00-05:00","location":"","site":"Neutral","link":"https://purduesports.com/sports/mens-basketball/schedule"}
    ]
}
with open(os.path.join(TEAM_DIR, "schedule.json"), "w") as f:
    json.dump(schedule, f, indent=2)

# --------- RANKINGS ----------
rankings = {
    "ap": {"rank": "1", "url": "https://apnews.com/hub/ap-top-25-college-basketball-poll", "updated": now_iso},
    "kenpom": {"rank": "2", "url": "https://kenpom.com/", "updated": now_iso},
    "updated": now_iso
}
with open(os.path.join(DATA_DIR, "rankings.json"), "w") as f:
    json.dump(rankings, f, indent=2)

# --------- BEAT LINKS ----------
beat = [
    {"title":"Hammer & Rails — Purdue Hoops","url":"https://www.hammerandrails.com/purdue-basketball"},
    {"title":"Gold and Black — MBB","url":"https://goldandblack.com"},
    {"title":"247Sports — Purdue Basketball","url":"https://247sports.com/college/purdue/"},
    {"title":"PurdueSports.com — MBB","url":"https://purduesports.com/sports/mens-basketball"}
]
with open(os.path.join(DATA_DIR, "beat_links.json"), "w") as f:
    json.dump(beat, f, indent=2)

print("✅ JSONs written successfully")