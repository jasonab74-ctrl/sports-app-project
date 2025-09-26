import os, json, yaml, feedparser
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

TRUST_WEIGHTS = {"official":1.0,"beat":0.9,"national":0.8,"local":0.75,"blog":0.6,"fan_forum":0.5}
RECENCY_HALFLIFE_HOURS = 18.0
DEDUP_TITLE_SIM_THRESHOLD = 85
DEFAULT_LIMIT = 200

FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TeamHubBot/1.0"
}

def recency_weight(dt):
    now = datetime.now(timezone.utc)
    hours = max(0, (now - dt).total_seconds()/3600.0)
    return 0.5 ** (hours / RECENCY_HALFLIFE_HOURS)

def canonicalize_url(url):
    if not url: return ""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def parse_dt(entry):
    for key in ("published","updated","created"):
        if entry.get(key + "_parsed"):
            try:
                return datetime(*entry.get(key + "_parsed")[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def score_item(it):
    trust = TRUST_WEIGHTS.get(it.get("trust_level","blog"), 0.6)
    rec = it.get("recency", 0.5)
    return 0.55*trust + 0.35*rec + 0.10*0.0

def dedupe(items):
    seen, out = set(), []
    for it in items:
        url = canonicalize_url(it["url"])
        if url in seen: 
            continue
        if any(fuzz.token_set_ratio(it["title"], k["title"]) >= DEDUP_TITLE_SIM_THRESHOLD for k in out):
            continue
        out.append(it); seen.add(url)
    return out

def extract_image(entry):
    for key in ("media_thumbnail","media_content","links"):
        val = entry.get(key)
        if isinstance(val, list):
            for v in val:
                href = v.get("url") or v.get("href")
                if href and href.startswith("http"):
                    return href
    return None

def collect_from_feedlist(team, feedlist):
    all_items = []
    for feed in feedlist:
        name, url = feed["name"], feed["url"]
        d = feedparser.parse(url, request_headers=FEED_HEADERS)
        for e in d.entries[:50]:
            title = e.get("title") or "(no title)"
            link = canonicalize_url(e.get("link") or e.get("id") or "")
            if not link: 
                continue
            dt = parse_dt(e)
            all_items.append({
                "team": team,
                "source": name,
                "source_type": feed.get("type","rss"),
                "trust_level": feed.get("trust_level","blog"),
                "title": title.strip(),
                "url": link,
                "guid": e.get("id") or e.get("guid") or link,
                "published_at": dt.isoformat(),
                "recency": recency_weight(dt),
                "image_url": extract_image(e),
                "author": e.get("author")
            })
    return all_items

def collect_team(team, feeds, out_file):
    # Try your configured feeds first
    all_items = collect_from_feedlist(team, feeds)

    # Fallback so the page is never empty
    if len(all_items) == 0:
        fallback = [
            {
              "name": "Google News (Purdue Basketball)",
              "url": "https://news.google.com/rss/search?q=Purdue+Boilermakers+basketball&hl=en-US&gl=US&ceid=US:en",
              "type": "rss", "trust_level": "national"
            },
            {
              "name": "YouTube (Purdue Basketball)",
              "url": "https://www.youtube.com/feeds/videos.xml?search_query=Purdue+Basketball",
              "type": "rss", "trust_level": "national"
            }
        ]
        all_items = collect_from_feedlist(team, fallback)

    all_items.sort(key=score_item, reverse=True)
    all_items = dedupe(all_items)[:DEFAULT_LIMIT]

    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "team": team,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": all_items
        }, f, indent=2, ensure_ascii=False)

def main():
    conf = yaml.safe_load(open("src/feeds.yaml", "r", encoding="utf-8"))
    teams_env = os.environ.get("TEAMS","").strip()
    teams = [t.strip() for t in teams_env.split(",") if t.strip()] if teams_env else list(conf.keys())
    if not teams:
        raise SystemExit("No teams specified and feeds.yaml is empty.")
    for team in teams:
        if team not in conf:
            continue
        collect_team(team, conf[team], f"static/teams/{team}/items.json")

if __name__ == "__main__":
    main()
