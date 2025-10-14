#!/usr/bin/env python3
"""
Collector for Boilermakers Hub

Outputs (and *never blanks*):
  static/data/news.json        -> top 10 most-recent Purdue MBB-focused headlines
  static/data/schedule.json    -> upcoming games (UTC ISO), next ~5
  static/data/rankings.json    -> AP, KenPom, links, updated ISO
  static/data/beat_links.json  -> pass-through (if present)

Key guarantees:
- All timestamps are strict ISO-8601 in UTC.
- If any fetch fails, last-good data is reused so UI never goes empty.
- Schedule prefers a canonical file at static/teams/purdue-mbb/schedule.json,
  otherwise it scrapes the official Purdue schedule (JSON-LD first).
- Rankings can be forced in static/config/rankings_overrides.json.

News filter uses *scoring* (not brittle regex). If fewer than 10 items pass,
it auto-relaxes (still blocking obvious football) so you always see 10 fresh stories.
"""

import os, json, re, time, tldextract, feedparser, requests
from datetime import datetime, timezone
from dateutil import parser as dtparse
from bs4 import BeautifulSoup

# ---------- paths ----------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "static", "data")
CFG_DIR  = os.path.join(ROOT, "static", "config")
TEAM_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------- constants ----------
OFFICIAL_SCHEDULE_URL = "https://purduesports.com/sports/mens-basketball/schedule"

DEFAULT_FEEDS = [
    "https://purduesports.com/rss?path=mbball",
    "https://www.hammerandrails.com/rss/index.xml",
    "https://www.espn.com/espn/rss/ncb/news",
    "https://www.cbssports.com/feeds/content/college-basketball/",
    "https://sports.yahoo.com/topics/college-basketball/rss/"
]

# News scoring vocabulary (can be tweaked in static/config/news_filter.json)
DEFAULT_FILTER = {
    "purdue_terms": [
        "purdue", "boilermaker", "boilermakers", "mackey", "west lafayette", "painter"
    ],
    "mbb_terms": [
        "basketball", "men's", "mens", "mbb", "cbb", "ncaa tournament", "big ten", "b1g", "guard", "forward", "center"
    ],
    "block_terms": [
        "football", "cfb", "nfl"
    ],
    "domain_boosts": {
        "purduesports.com": 4,
        "hammerandrails.com": 3,
        "goldandblack.com": 3,
        "247sports.com": 2,
        "yahoo.com": 1,
        "yahoo.com.cn": 1,
        "espn.com": 1,
        "cbssports.com": 1
    },
    "min_main_score": 5,   # normal accept threshold
    "min_relaxed_score": 3 # relaxed threshold if < 10 made it through
}

SECTION_MAP = {
    "purduesports.com": "official",
    "hammerandrails.com": "insiders",
    "goldandblack.com": "insiders",
    "247sports.com": "insiders",
}

# ---------- helpers ----------
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def iso(dtval):
    if not dtval:
        return None
    try:
        return dtparse.parse(dtval).astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback

def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def host_of(url):
    try:
        t = tldextract.extract(url)
        h = ".".join([p for p in [t.domain, t.suffix] if p])
        return h.lower()
    except Exception:
        return ""

def guess_section(url):
    h = host_of(url)
    for dom, sec in SECTION_MAP.items():
        if h.endswith(dom):
            return sec
    return "national"

# ---------- news: config ----------
def load_filter_cfg():
    cfg = read_json(os.path.join(CFG_DIR, "news_filter.json"), {})
    if not isinstance(cfg, dict): cfg = {}
    merged = DEFAULT_FILTER.copy()
    # shallow merge for lists/dicts
    for k, v in cfg.items():
        if isinstance(v, list) and isinstance(merged.get(k), list):
            merged[k] = v
        elif isinstance(v, dict) and isinstance(merged.get(k), dict):
            base = merged[k].copy()
            base.update(v)
            merged[k] = base
        else:
            merged[k] = v
    # compile
    merged["_purdue_re"] = re.compile("|".join(map(re.escape, merged["purdue_terms"])), re.I)
    merged["_mbb_re"]    = re.compile("|".join(map(re.escape, merged["mbb_terms"])), re.I)
    merged["_block_re"]  = re.compile("|".join(map(re.escape, merged["block_terms"])), re.I)
    return merged

def first_image_from_entry(entry):
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    if isinstance(media, list) and media:
        u = media[0].get("url")
        if u: return u

    content = ""
    if "content" in entry and entry["content"]:
        content = entry["content"][0].get("value") or ""
    elif "summary" in entry:
        content = entry.get("summary") or ""

    if content:
        soup = BeautifulSoup(content, "lxml")
        tag = soup.find("img")
        if tag and tag.get("src"):
            return tag.get("src")

    link = entry.get("link")
    if not link:
        return None
    try:
        r = requests.get(link, timeout=6, headers={"User-Agent":"Mozilla/5.0 (Actions)"})
        if r.ok:
            soup = BeautifulSoup(r.text, "lxml")
            og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name":"og:image"})
            if og and og.get("content"):
                return og.get("content")
    except Exception:
        pass
    return None

def load_feed_urls():
    cfg_list = read_json(os.path.join(CFG_DIR, "news_feeds.json"), [])
    return cfg_list if (isinstance(cfg_list, list) and cfg_list) else DEFAULT_FEEDS

def score_article(text, url, fcfg):
    """
    Returns (score, reasons)
    Scoring: rewards Purdue + MBB context, boosts trusted domains, penalizes football.
    """
    text_l = (text or "").lower()
    urlhost = host_of(url)

    score = 0
    reasons = []

    # block terms
    if fcfg["_block_re"].search(text_l):
        score -= 4
        reasons.append("football-block")

    # Purdue
    if fcfg["_purdue_re"].search(text_l):
        score += 3
        reasons.append("purdue")

    # MBB / basketball context
    if fcfg["_mbb_re"].search(text_l):
        score += 3
        reasons.append("mbb")

    # domain boost
    for dom, boost in fcfg["domain_boosts"].items():
        if urlhost.endswith(dom):
            score += boost
            reasons.append(f"boost:{dom}")
            break

    return score, reasons

def collect_news():
    fcfg = load_filter_cfg()
    feeds = load_feed_urls()
    raw = []

    for u in feeds:
        try:
            feed = feedparser.parse(u)
            for e in feed.entries[:50]:
                title = (e.get("title") or "").strip()
                link  = e.get("link")  or ""
                if not title or not link:
                    continue
                summary = e.get("summary") or ""
                text = f"{title} {summary}"
                ts = iso(e.get("published") or e.get("updated")) or now_iso()
                img = first_image_from_entry(e)
                sec = guess_section(link)
                score, reasons = score_article(text, link, fcfg)
                raw.append({
                    "title": title,
                    "url": link,
                    "source": host_of(link),
                    "section": sec,
                    "image": img or None,
                    "ts": ts,
                    "_score": score,
                    "_reasons": reasons
                })
        except Exception:
            continue

    # Deduplicate by URL, keep highest score
    by_url = {}
    for it in raw:
        u = it["url"]
        if (u not in by_url) or (it["_score"] > by_url[u]["_score"]):
            by_url[u] = it
    items = list(by_url.values())

    # 1) strict-ish pass
    main_thr = DEFAULT_FILTER["min_main_score"]
    strict = [x for x in items if x["_score"] >= main_thr]

    # 2) if < 10, try relaxed (but still block football-heavy)
    if len(strict) < 10:
        relaxed_thr = DEFAULT_FILTER["min_relaxed_score"]
        relaxed = [
            x for x in items
            if x["_score"] >= relaxed_thr and "football-block" not in x["_reasons"]
        ]
        # keep top by score
        relaxed.sort(key=lambda z: (z["_score"], z["ts"]), reverse=True)
        chosen = []
        seen = set()
        for z in strict + relaxed:
            if z["url"] in seen: continue
            chosen.append(z); seen.add(z["url"])
            if len(chosen) == 10: break
    else:
        chosen = sorted(strict, key=lambda z: (z["_score"], z["ts"]), reverse=True)[:10]

    # 3) final shape (strip debug keys)
    out = []
    for x in chosen[:10]:
        out.append({
            "title": x["title"],
            "url": x["url"],
            "source": x["source"],
            "section": x["section"],
            "image": x["image"],
            "ts": x["ts"]
        })

    # sort by time (desc) to show “most recent” first; score has already influenced selection
    out.sort(key=lambda k: k["ts"], reverse=True)
    return out

# ---------- schedule ----------
def normalize_game(opponent, site, tip_iso, venue, city, state, url):
    return {
        "opponent": opponent or "TBD",
        "site": site or "Neutral",
        "tip": tip_iso,  # UTC ISO
        "venue": venue or "",
        "city": city or "",
        "state": state or "",
        "url": url or ""
    }

def read_canonical_schedule():
    path = os.path.join(TEAM_DIR, "schedule.json")
    if os.path.exists(path):
        arr = read_json(path, [])
        out = []
        for g in arr:
            out.append(normalize_game(
                g.get("opponent"), g.get("site"),
                iso(g.get("tip") or g.get("ts")),
                g.get("venue"), g.get("city"), g.get("state"),
                g.get("url")
            ))
        return out
    return None

def scrape_schedule_from_official():
    try:
        r = requests.get(OFFICIAL_SCHEDULE_URL, timeout=15, headers={"User-Agent":"Mozilla/5.0 (Actions)"})
        if not r.ok: raise RuntimeError("status")
        soup = BeautifulSoup(r.text, "lxml")

        # JSON-LD first
        jsonld = []
        for s in soup.find_all("script", attrs={"type":"application/ld+json"}):
            try:
                data = json.loads(s.string or s.text or "{}")
                if isinstance(data, dict): jsonld.append(data)
                elif isinstance(data, list): jsonld.extend(data)
            except Exception:
                pass

        games = []
        for block in jsonld:
            candidates = []
            if isinstance(block, dict) and "@graph" in block and isinstance(block["@graph"], list):
                candidates = block["@graph"]
            elif isinstance(block, dict):
                candidates = [block]

            for ev in candidates:
                if not isinstance(ev, dict): continue
                if ev.get("@type") not in ("SportsEvent","Event"): continue
                name     = ev.get("name") or ""
                start    = iso(ev.get("startDate"))
                loc      = ev.get("location") or {}
                venue, city, state = "", "", ""
                if isinstance(loc, dict):
                    venue = (loc.get("name") or "") if isinstance(loc.get("name"), str) else ""
                    adr   = loc.get("address") or {}
                    if isinstance(adr, dict):
                        city  = adr.get("addressLocality") or ""
                        state = adr.get("addressRegion") or ""
                link = ev.get("url") or OFFICIAL_SCHEDULE_URL
                site = "Neutral"
                if city.lower().startswith("west lafayette"): site = "Home"
                elif city: site = "Away"
                games.append(normalize_game(name, site, start, venue, city, state, link))

        if games:
            now = datetime.now(timezone.utc)
            fut = [g for g in games if g["tip"] and dtparse.parse(g["tip"]) >= now]
            fut.sort(key=lambda g: g["tip"])
            return (fut or games)[:5]

    except Exception:
        pass
    return None

def load_schedule():
    canon = read_canonical_schedule()
    if canon: return canon
    scr = scrape_schedule_from_official()
    if scr: return scr
    last = read_json(os.path.join(DATA_DIR, "schedule.json"), [])
    if last: return last
    # tiny seed as absolute fallback
    return [normalize_game("Kentucky (Exhibition)", "Away", now_iso(), "Rupp Arena", "Lexington","KY", OFFICIAL_SCHEDULE_URL)]

# ---------- rankings ----------
def load_rankings():
    path = os.path.join(DATA_DIR, "rankings.json")
    obj  = read_json(path, {})

    obj.setdefault("ap", None)
    obj.setdefault("kenpom", None)
    obj.setdefault("ap_link", "https://apnews.com/hub/ap-top-25-college-basketball-poll")
    obj.setdefault("kenpom_link", "https://kenpom.com/")

    over_path = os.path.join(CFG_DIR, "rankings_overrides.json")
    ov = read_json(over_path, {})
    if isinstance(ov, dict):
        if ov.get("ap") is not None: obj["ap"] = ov.get("ap")
        if ov.get("kenpom") is not None: obj["kenpom"] = ov.get("kenpom")
        if ov.get("ap_link"): obj["ap_link"] = ov["ap_link"]
        if ov.get("kenpom_link"): obj["kenpom_link"] = ov["kenpom_link"]

    obj["updated"] = now_iso()
    return obj

# ---------- beats ----------
def load_beats():
    return read_json(os.path.join(DATA_DIR, "beat_links.json"), [])

# ---------- main ----------
def main():
    last_news  = read_json(os.path.join(DATA_DIR,"news.json"), [])
    last_sched = read_json(os.path.join(DATA_DIR,"schedule.json"), [])
    last_rank  = read_json(os.path.join(DATA_DIR,"rankings.json"), {})
    last_beats = read_json(os.path.join(DATA_DIR,"beat_links.json"), [])

    try:
        news = collect_news() or last_news
    except Exception:
        news = last_news

    try:
        sched = load_schedule() or last_sched
    except Exception:
        sched = last_sched

    try:
        rank = load_rankings() or last_rank
    except Exception:
        rank = last_rank

    try:
        beats = load_beats() or last_beats
    except Exception:
        beats = last_beats

    write_json(os.path.join(DATA_DIR,"news.json"), news)
    write_json(os.path.join(DATA_DIR,"schedule.json"), sched)
    write_json(os.path.join(DATA_DIR,"rankings.json"), rank)
    write_json(os.path.join(DATA_DIR,"beat_links.json"), beats)

if __name__ == "__main__":
    main()
