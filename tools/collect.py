#!/usr/bin/env python3
import json, os, sys, time
from datetime import datetime, timezone
from dateutil import parser

DATA_DIR = "static/data"
os.makedirs(DATA_DIR, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback

def iso(v):
    if not v: return None
    try:
        return parser.parse(v).astimezone(timezone.utc).isoformat()
    except Exception:
        try:
            # unix seconds
            return datetime.fromtimestamp(float(v), tz=timezone.utc).isoformat()
        except Exception:
            return None

# -------------------------
# Seed providers (safe defaults)
# Replace with real fetchers as you wire sources.
# -------------------------

def seed_news():
    # 10 examples to prove UI; replace as you wire real feeds.
    return [
      {
        "title":"Purdue announces exhibition details vs. Kentucky",
        "url":"https://purduesports.com/",
        "source":"PurdueSports.com",
        "section":"official",
        "image":None,
        "ts": now_iso()
      },
      {
        "title":"Practice report: Guards battle for minutes at Mackey",
        "url":"https://www.hammerandrails.com/",
        "source":"Hammer & Rails",
        "section":"insiders",
        "image":None,
        "ts": now_iso()
      }
    ]

def seed_schedule():
    # 3 upcoming examples
    return [
      {
        "opponent":"Kentucky (Exhibition)",
        "site":"Away",
        "tip": (datetime.now(timezone.utc)).isoformat(),
        "venue":"Rupp Arena",
        "city":"Lexington",
        "state":"KY",
        "url":"https://purduesports.com/"
      }
    ]

def seed_rankings():
    return {
      "ap": 1,
      "kenpom": 2,
      "ap_link": "https://apnews.com/hub/ap-top-25-college-basketball-poll",
      "kenpom_link": "https://kenpom.com/",
      "updated": now_iso()
    }

def seed_beats():
    return [
      {"title":"Predicting Purdue Men’s Basketball Starting Lineup","url":"https://www.hammerandrails.com/"},
      {"title":"The Cost to Watch Purdue Men’s Basketball","url":"https://www.hammerandrails.com/"}
    ]

def normalize_news(items):
    out = []
    for it in items:
        if not it or not it.get("title") or not it.get("url"): continue
        out.append({
            "title": it["title"],
            "url": it["url"],
            "source": it.get("source") or "",
            "section": (it.get("section") or "national").lower(),
            "image": it.get("image") or None,
            "ts": iso(it.get("ts") or it.get("date") or it.get("published_at") or now_iso())
        })
    # sort newest first; trim 10
    out.sort(key=lambda x: x["ts"] or "", reverse=True)
    return out[:10]

def normalize_sched(items):
    out=[]
    for g in items or []:
        out.append({
            "opponent": g.get("opponent") or "TBD",
            "site": g.get("site") or "Neutral",
            "tip": iso(g.get("tip") or g.get("ts")),
            "venue": g.get("venue") or "",
            "city": g.get("city") or "",
            "state": g.get("state") or "",
            "url": g.get("url") or ""
        })
    # keep only with valid future tip; trim 5 handled at UI too
    out = [g for g in out if g["tip"]]
    out.sort(key=lambda x: x["tip"])
    return out

def main():
    # Existing (last good) payloads
    last_news = read_json(os.path.join(DATA_DIR,"news.json"), [])
    last_sched = read_json(os.path.join(DATA_DIR,"schedule.json"), [])
    last_rank  = read_json(os.path.join(DATA_DIR,"rankings.json"), {})
    last_beats = read_json(os.path.join(DATA_DIR,"beat_links.json"), [])

    # In this starter, we just use seeds.
    news = normalize_news(seed_news()) or last_news
    sched = normalize_sched(seed_schedule()) or last_sched
    rank = seed_rankings() or last_rank
    beats = seed_beats() or last_beats

    # Persist
    write_json(os.path.join(DATA_DIR,"news.json"), news)
    write_json(os.path.join(DATA_DIR,"schedule.json"), sched)
    write_json(os.path.join(DATA_DIR,"rankings.json"), rank)
    write_json(os.path.join(DATA_DIR,"beat_links.json"), beats)

if __name__ == "__main__":
    main()