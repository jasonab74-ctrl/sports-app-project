import os, json, yaml, feedparser, requests, re, tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

# ---------------- Tunables ----------------
RECENCY_HALFLIFE_HOURS = 18.0
DEDUP_TITLE_SIM_THRESHOLD = 85
MAX_AGE_DAYS = 10                      # drop items older than this
FEED_HEADERS = {"User-Agent": "Mozilla/5.0 TeamHubBot/1.0"}
TRUST_WEIGHTS = {"official":1.0,"beat":0.9,"national":0.8,"local":0.75,"blog":0.6,"fan_forum":0.5}
TOP_LIMIT = 200                        # internal cap before writing

# --------------- Helpers -----------------
def canonicalize_url(url):
    if not url: return ""
    p = urlparse(url)
    return urlunparse((p.scheme,p.netloc,p.path,"","",""))

def parse_dt(entry):
    for key in ("published_parsed","updated_parsed","created_parsed"):
        val = getattr(entry,key,None) or entry.get(key)
        if val:
            try: return datetime(*val[:6],tzinfo=timezone.utc)
            except: pass
    return datetime.now(timezone.utc)

def normalize_item(feed_name,trust_level,entry):
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary = (entry.get("summary") or entry.get("description") or "").strip()
    date = parse_dt(entry)
    image = None
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media,list) and media: image = media[0].get("url")
    return {
        "type":"news","source":feed_name,"trust":trust_level,
        "title":title,"link":link,"date":date.isoformat(),
        "summary":summary[:500],"image":image
    }

def dedup_items(items):
    out, seen_urls = [], set()
    for it in items:
        url = canonicalize_url(it.get("link"))
        title = (it.get("title") or "").strip().lower()
        if url and url in seen_urls: continue
        dup = any(fuzz.token_set_ratio(title,(oi.get("title") or "").lower())>=DEDUP_TITLE_SIM_THRESHOLD for oi in out)
        if not dup:
            out.append(it)
            if url: seen_urls.add(url)
    return out

def recency_weight(dt):
    hours = max(0, (datetime.now(timezone.utc) - dt).total_seconds()/3600.0)
    return 0.5 ** (hours / RECENCY_HALFLIFE_HOURS)

def score_item(it):
    trust = TRUST_WEIGHTS.get(str(it.get("trust") or "").lower(),0.6)
    try: dt = datetime.fromisoformat(it["date"].replace("Z","+00:00"))
    except: dt = datetime.now(timezone.utc)
    return 0.7*recency_weight(dt) + 0.3*trust

def atomic_write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=os.path.dirname(path), encoding="utf-8") as tmp:
        json.dump(obj, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)  # atomic on Linux runners

def read_existing(path):
    if not os.path.exists(path): return []
    try:
        j=json.load(open(path,encoding="utf-8"))
        return j.get("items",[]) if isinstance(j,dict) else []
    except: return []

def newest_dt(items):
    if not items: return None
    latest=None
    for it in items:
        try:
            d=datetime.fromisoformat(it["date"].replace("Z","+00:00"))
            if (latest is None) or (d>latest): latest=d
        except: pass
    return latest

# --------------- Collector ----------------
def collect_team(team_slug, feeds, out_path, limit=TOP_LIMIT):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    # 1) Fetch fresh
    fresh=[]
    for f in feeds:
        name=f.get("name","Source"); url=f.get("url"); trust=f.get("trust_level","blog")
        if not url: continue
        d=feedparser.parse(url, request_headers=FEED_HEADERS)
        for e in d.entries[:50]:
            it=normalize_item(name,trust,e)
            try:
                dt=datetime.fromisoformat(it["date"].replace("Z","+00:00"))
            except:
                dt=datetime.now(timezone.utc)
            if dt < cutoff:  # too old
                continue
            fresh.append(it)

    # 2) Read what’s currently live
    current = read_existing(out_path)
    newest_current = newest_dt(current)
    newest_fresh   = newest_dt(fresh)

    # 3) If this run produced nothing or clearly older headlines, DO NOT roll back
    if not fresh:
        print(f"[{team_slug}] Fresh=0 → keep existing ({len(current)} items).")
        return
    if newest_current and newest_fresh and (newest_fresh < newest_current):
        print(f"[{team_slug}] Fresh newest {newest_fresh} < Current newest {newest_current} → keep existing.")
        return

    # 4) Merge: prefer fresh, then old, dedup, score, limit
    merged = dedup_items(fresh + current)
    merged.sort(key=score_item, reverse=True)
    merged = merged[:limit]

    atomic_write_json(out_path, {"items": merged})
    print(f"[{team_slug}] wrote {len(merged)} items (fresh {len(fresh)} + current {len(current)} merged) -> {out_path}")

# --------------- Rankings -----------------
def fetch_ap_rank():
    try:
        r=requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/rankings",
            timeout=10, headers=FEED_HEADERS
        ); r.raise_for_status()
        data=r.json()
        for poll in data.get("rankings",[]):
            for t in poll.get("ranks",[]):
                if "Purdue" in t.get("team",{}).get("displayName",""):
                    val=t.get("current")
                    return int(val) if isinstance(val,int) or (isinstance(val,str) and val.isdigit()) else None
    except Exception as e:
        print("AP fetch error:", e)
    return None

def fetch_kenpom_rank():
    try:
        r=requests.get("https://kenpom.com/", timeout=10, headers=FEED_HEADERS); r.raise_for_status()
        m=re.search(r"Purdue</a></td><td[^>]*>(\d+)</td>", r.text)
        if m: return int(m.group(1))
    except Exception as e:
        print("KenPom fetch error:", e)
    return None

def update_widgets():
    path="static/widgets.json"
    data={"ap_rank":"—","kenpom_rank":"—","nil":[]}
    if os.path.exists(path):
        try: data=json.load(open(path,encoding="utf-8"))
        except: pass
    ap=fetch_ap_rank(); kp=fetch_kenpom_rank()
    if ap is not None: data["ap_rank"]=str(ap)
    if kp is not None: data["kenpom_rank"]=str(kp)
    atomic_write_json(path, data)
    print(f"widgets.json -> AP:{data['ap_rank']} KP:{data['kenpom_rank']}")

# --------------- Main ---------------------
def main():
    conf=yaml.safe_load(open("src/feeds.yaml","r",encoding="utf-8"))
    teams_env=os.environ.get("TEAMS","").strip()
    teams=[t.strip() for t in teams_env.split(",") if t.strip()] if teams_env else list(conf.keys())
    if not teams: raise SystemExit("No teams specified and feeds.yaml is empty.")
    for team in teams:
        if team not in conf:
            print(f"Team {team} not in feeds.yaml; skipping.")
            continue
        collect_team(team, conf[team], f"static/teams/{team}/items.json")
    update_widgets()

if __name__=="__main__":
    main()