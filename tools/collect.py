#!/usr/bin/env python3
"""
Collector for Boilermakers Hub

- Builds four files the site reads:
    static/data/news.json        (top 10 most-recent Purdue MBB stories)
    static/data/schedule.json    (upcoming games; keep last good if unknown)
    static/data/rankings.json    (AP, KenPom values + links + updated iso)
    static/data/beat_links.json  (optional curated links)

- Never blanks the site:
  * If a fetch fails, we reuse the last good JSON on disk.
  * All timestamps are strict ISO 8601 (UTC).

- News sources:
  * Reads RSS/Atom feeds (fast & reliable on Actions).
  * Default list is baked in; you can override/extend by creating:
        static/config/news_feeds.json
    with: ["https://...", "https://..."]

- Filters:
  * Keep items that look like Purdue Men's Basketball.
  * Drop Football.
"""
import os, json, re, time, tldextract, feedparser, requests
from datetime import datetime, timezone
from dateutil import parser as dtparse
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "static", "data")
CFG_DIR  = os.path.join(ROOT, "static", "config")
os.makedirs(DATA_DIR, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

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

def iso(dtval):
    if not dtval:
        return None
    try:
        return dtparse.parse(dtval).astimezone(timezone.utc).isoformat()
    except Exception:
        return None

# -----------------------------
# NEWS
# -----------------------------
DEFAULT_FEEDS = [
    # Official
    "https://purduesports.com/rss?path=mbball",            # Purdue MBB (official) – if not valid, it will just be skipped
    # Insiders (change as you like)
    "https://www.hammerandrails.com/rss/index.xml",
    # National (basketball heavy)
    "https://www.espn.com/espn/rss/ncb/news",
    "https://www.cbssports.com/feeds/content/college-basketball/",
    "https://sports.yahoo.com/topics/college-basketball/rss/",
]

INCLUDE_PAT = re.compile(
    r"(purdue|boilermaker|mackey|big ten|b1g).*?(basketball|mbb|men'?s)",
    re.I
)
EXCLUDE_PAT = re.compile(r"football|cfb|nfl", re.I)

SECTION_MAP = {
    "purduesports.com": "official",
    "hammerandrails.com": "insiders",
    "goldandblack.com": "insiders",
    "247sports.com": "insiders",
}

def host_of(url):
    try:
        t = tldextract.extract(url)
        host = ".".join([p for p in [t.domain, t.suffix] if p])
        return host.lower()
    except Exception:
        return ""

def guess_section(url):
    h = host_of(url)
    for domain, sec in SECTION_MAP.items():
        if h.endswith(domain):
            return sec
    return "national"

def first_image_from_entry(entry):
    # Media thumbnails (if present)
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    if isinstance(media, list) and media:
        u = media[0].get("url")
        if u: return u
    # Try content HTML
    content = ""
    if "content" in entry and entry["content"]:
        content = entry["content"][0].get("value") or ""
    elif "summary" in entry:
        content = entry.get("summary") or ""

    img = None
    if content:
        soup = BeautifulSoup(content, "lxml")
        tag = soup.find("img")
        if tag and tag.get("src"):
            img = tag.get("src")

    if img:
        return img

    # As a last resort, fetch the page and read og:image (best-effort, time-limited)
    link = entry.get("link")
    if not link:
        return None
    try:
        r = requests.get(link, timeout=6, headers={"User-Agent":"Mozilla/5.0 (Actions)"})
        if not r.ok: return None
        soup = BeautifulSoup(r.text, "lxml")
        og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name":"og:image"})
        if og and og.get("content"):
            return og.get("content")
    except Exception:
        pass
    return None

def load_feed_urls():
    cfg_path = os.path.join(CFG_DIR, "news_feeds.json")
    feeds = read_json(cfg_path, [])
    if isinstance(feeds, list) and feeds:
        return feeds
    return DEFAULT_FEEDS

def collect_news():
    urls = load_feed_urls()
    items = []
    for u in urls:
        try:
            feed = feedparser.parse(u)
            for e in feed.entries[:50]:  # don’t go crazy
                title = e.get("title") or ""
                link = e.get("link") or ""
                if not title or not link: 
                    continue
                text = f"{title} {e.get('summary','')}"
                if not INCLUDE_PAT.search(text):
                    continue
                if EXCLUDE_PAT.search(text):
                    continue
                published = e.get("published") or e.get("updated") or None
                ts = iso(published) or now_iso()
                src = host_of(link)
                section = guess_section(link)
                img = first_image_from_entry(e)

                items.append({
                    "title": title.strip(),
                    "url": link,
                    "source": src or "",
                    "section": section,
                    "image": img or None,
                    "ts": ts
                })
        except Exception:
            # skip problematic feed; others will fill in
            continue

    # de-dupe by URL
    seen = set()
    uniq = []
    for it in items:
        if it["url"] in seen: 
            continue
        seen.add(it["url"])
        uniq.append(it)

    # newest first; keep 10
    uniq.sort(key=lambda x: x["ts"], reverse=True)
    return uniq[:10]

# -----------------------------
# SCHEDULE / RANKINGS / BEAT LINKS
# -----------------------------
def load_schedule():
    """
    If you already have a canonical schedule JSON somewhere in the repo
    (e.g., static/teams/purdue-mbb/schedule.json), read and normalize it.
    Otherwise, keep last good or a tiny seed.
    """
    # Optional: read a canonical schedule file if present
    team_sched_path = os.path.join(ROOT, "static", "teams", "purdue-mbb", "schedule.json")
    if os.path.exists(team_sched_path):
        try:
            arr = read_json(team_sched_path, [])
            out = []
            for g in arr:
                out.append({
                    "opponent": g.get("opponent") or "TBD",
                    "site": g.get("site") or "Neutral",
                    "tip": iso(g.get("tip") or g.get("ts")),
                    "venue": g.get("venue") or "",
                    "city": g.get("city") or "",
                    "state": g.get("state") or "",
                    "url": g.get("url") or ""
                })
            # keep future only in UI; here we just normalize
            return out
        except Exception:
            pass

    # Fallback: last good on disk or a tiny seed
    last = read_json(os.path.join(DATA_DIR,"schedule.json"), [])
    if last:
        return last

    seed = [{
        "opponent":"Kentucky (Exhibition)",
        "site":"Away",
        "tip": now_iso(),
        "venue":"Rupp Arena",
        "city":"Lexington","state":"KY",
        "url":"https://purduesports.com/"
    }]
    return seed

def load_rankings():
    """
    If a rankings.json already exists, keep it and refresh 'updated'.
    (Scraping AP/KenPom live is brittle; this guarantees non-empty values.)
    You can manually bump values by committing to static/data/rankings.json
    or extend this function later with a reliable source.
    """
    path = os.path.join(DATA_DIR, "rankings.json")
    obj = read_json(path, {})
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("ap", None)
    obj.setdefault("kenpom", None)
    obj.setdefault("ap_link", "https://apnews.com/hub/ap-top-25-college-basketball-poll")
    obj.setdefault("kenpom_link", "https://kenpom.com/")
    obj["updated"] = now_iso()
    return obj

def load_beats():
    path = os.path.join(DATA_DIR, "beat_links.json")
    arr = read_json(path, [])
    if not isinstance(arr, list):
        arr = []
    return arr

# -----------------------------
# MAIN
# -----------------------------
def main():
    # Last-good snapshots (used if today’s fetch fails)
    last_news = read_json(os.path.join(DATA_DIR,"news.json"), [])
    last_sched = read_json(os.path.join(DATA_DIR,"schedule.json"), [])
    last_rank  = read_json(os.path.join(DATA_DIR,"rankings.json"), {})
    last_beats = read_json(os.path.join(DATA_DIR,"beat_links.json"), [])

    # Build fresh
    try:
        news = collect_news()
        if not news:
            news = last_news
    except Exception:
        news = last_news

    try:
        sched = load_schedule()
        if not isinstance(sched, list):
            sched = last_sched
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

    # Persist
    write_json(os.path.join(DATA_DIR,"news.json"), news)
    write_json(os.path.join(DATA_DIR,"schedule.json"), sched)
    write_json(os.path.join(DATA_DIR,"rankings.json"), rank)
    write_json(os.path.join(DATA_DIR,"beat_links.json"), beats)

if __name__ == "__main__":
    main()