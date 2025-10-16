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
    if not url:
        return ""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def parse_dt(entry):
    for key in ("published_parsed","updated_parsed","created_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def normalize_item(feed_name, trust_level, entry):
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary = (entry.get("summary") or entry.get("description") or "").strip()
    date = parse_dt(entry)
    image = None

    media = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media, list) and media:
        image = media[0].get("url")

    return {
        "type": "news",
        "source": feed_name,
        "trust": trust_level,
        "title": title,
        "link": link,
        "date": date.isoformat(),
        "summary": summary[:500],
        "image": image
    }

def dedup_items(items):
    out = []
    seen_urls = set()
    for it in items:
        url = canonicalize_url(it.get("link"))
        title = (it.get("title") or "").strip().lower()
        if url and url in seen_urls:
            continue
        duplicate = False
        for oi in out:
            if fuzz.token_set_ratio(title, (oi.get("title") or "").strip().lower()) >= DEDUP_TITLE_SIM_THRESHOLD:
                duplicate = True
                break
        if not duplicate:
            out.append(it)
            if url:
                seen_urls.add(url)
    return out

def score_item(it):
    trust = TRUST_WEIGHTS.get(str(it.get("trust") or "").lower(), 0.6)
    try:
        dt = datetime.fromisoformat(it["date"].replace("Z","+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    recency = recency_weight(dt)
    return 0.7*recency + 0.3*trust

def collect_team(team_slug, feeds, out_path, limit=DEFAULT_LIMIT):
    import ssl
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except Exception:
        pass

    all_items = []
    for f in feeds:
        name = f.get("name","Source")
        url = f.get("url")
        trust = f.get("trust_level","blog")
        if not url:
            continue
        d = feedparser.parse(url, request_headers=FEED_HEADERS)
        for e in d.entries[:50]:
            it = normalize_item(name, trust, e)
            all_items.append(it)

    all_items = dedup_items(all_items)
    all_items.sort(key=score_item, reverse=True)
    all_items = all_items[:limit]

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"items": all_items}, f, indent=2, ensure_ascii=False)

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
