#!/usr/bin/env python3
# tools/collect.py
#
# Builds static/data/news.json with the 10 most-recent Purdue MBB headlines
# (hero + 9). Strong football filters, Purdue/MBB heuristics, and safe
# fallback sources so we consistently reach 10 items.

import os, re, json, time, hashlib, html
from urllib.parse import urlparse
import feedparser, requests

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "static", "data")
SRC_PATH = os.path.join(DATA_DIR, "sources.json")
OUT_PATH = os.path.join(DATA_DIR, "news.json")

# ----------------- Keyword model (tightened) -----------------
# Positive signals for Purdue Men's Basketball
MBB_POSITIVE = [
    r"\bmen'?s?\s+basketball\b", r"\bmbb\b", r"\bbasketball\b", r"\bhoops?\b",
    r"\bmatt\s+painter\b", r"\bmackey\s+arena\b", r"\bpaint\s+crew\b",
    r"\bzach\s+edey\b", r"\bbraden\s+smith\b", r"\bfletcher\s+loyer\b",
    r"\bcaleb\s+furst\b", r"\bbig\s+ten\b", r"\bncaa\b", r"\bmarch\s+madness\b",
    r"\bexhibition\b", r"\bregular\s+season\b", r"\btournament\b",
]
# Negative: football & gridiron terms (expanded)
FOOTBALL_NEG = [
    r"\bfootball\b", r"\bfball\b", r"\bnfl\b", r"\bqb\b", r"\bquarterback\b",
    r"\brunning\s*back\b", r"\bwide\s*receiver\b", r"\boffensive\s*line\b",
    r"\bdefensive\s*line\b", r"\btouchdown\b", r"\bfield\s*goal\b",
    r"\bcoach\s+ryan\s+walters\b", r"\bhudson\s+card\b", r"\bross-ade\b",
]
# Purdue anchor
PURDUE_CORE = [r"\bpurdue\b", r"\bboilermakers?\b", r"\bwest\s+lafayette\b"]

def compile_all(rx_list): return [re.compile(rx, re.I) for rx in rx_list]
RX_MBB = compile_all(MBB_POSITIVE)
RX_FB  = compile_all(FOOTBALL_NEG)
RX_PU  = compile_all(PURDUE_CORE)

# URL path hints for MBB
PATH_HINTS = [
    "/mbb", "/m-basketball", "/mens-basketball", "/men-basketball",
    "/basketball/", "/college-basketball/", "/ncaa-basketball/"
]
# URL path hints for football to hard-exclude
PATH_FB = ["/football", "/cfb", "/college-football", "/ncaa-football"]

# ----------------- helpers -----------------
def load_json(path, default=None):
    if not os.path.exists(path): return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def domain(u):
    try:
        return (urlparse(u).hostname or "").replace("www.","")
    except:
        return ""

def clean_text(s):
    if not s: return ""
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def sha16(s): return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]

def ts_from_entry(e):
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        if e.get(k):
            return int(time.mktime(e[k])) * 1000
    return int(time.time() * 1000)

IMG_RX = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
def img_from_html(h):
    if not isinstance(h, str): return None
    m = IMG_RX.search(h)
    return m.group(1) if m else None

def first_image(entry):
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    for m in media:
        if m.get("url"): return m["url"]
    if entry.get("content"):
        for c in entry["content"]:
            u = img_from_html(c.get("value") or "")
            if u: return u
    u = img_from_html(entry.get("summary") or "")
    if u: return u
    sd = entry.get("summary_detail") or {}
    if "html" in (sd.get("type") or ""):
        u = img_from_html(sd.get("value") or "")
        if u: return u
    return None

def og_image(link):
    try:
        r = requests.get(link, timeout=6, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code != 200: return None
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', r.text, re.I)
        if m: return m.group(1)
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', r.text, re.I)
        return m.group(1) if m else None
    except Exception:
        return None

def fetch_feed(url, tier):
    try:
        fp = feedparser.parse(url)
    except Exception:
        return []
    items=[]
    for e in fp.entries:
        link = e.get("link") or ""
        title = clean_text(e.get("title"))
        summary = clean_text(e.get("summary") or (e.get("content",[{}])[0].get("value") if e.get("content") else ""))
        src = domain(link) or domain(fp.href or url)
        ts = ts_from_entry(e)
        img = first_image(e) or (og_image(link) if link else None)
        items.append({
            "id": sha16(link or title),
            "title": title, "summary": summary, "link": link,
            "source": src, "tier": tier, "type": "article",
            "ts": ts, "image": img, "paywall": False
        })
    return items

def uniq(items):
    seen=set(); out=[]
    for it in sorted(items, key=lambda x: x["ts"], reverse=True):
        k=(it["title"], it["link"])
        if k in seen: continue
        seen.add(k); out.append(it)
    return out

def any_re(rx_list, text): return any(rx.search(text) for rx in rx_list)

def looks_basketball(item):
    """Return True if item is Purdue MBB; False if football/other."""
    link = item.get("link","")
    path = urlparse(link).path.lower()
    # Hard path exclusions for football
    if any(seg in path for seg in PATH_FB):
        return False

    blob = " ".join([
        item.get("title",""), item.get("summary",""),
        link, item.get("source","")
    ]).lower()

    # Must be Purdue-related unless it's the official athletics site
    is_purdue_anchor = any_re(RX_PU, blob) or "purduesports.com" in (item.get("source") or "")
    if not is_purdue_anchor:
        return False

    # If football words appear AND no basketball cues, drop it
    looks_fb = any_re(RX_FB, blob)
    looks_bb = any_re(RX_MBB, blob) or any(h in path for h in PATH_HINTS)
    if looks_fb and not looks_bb:
        return False

    # Prefer basketball: require at least some basketball signal
    return looks_bb

# ----------------- sources (merge with fallbacks) -----------------
FALLBACK = {
    "official": [
        # SIDEARM Sports feeds are typically path-based like this:
        "https://purduesports.com/rss.aspx?path=mbball",
    ],
    "insiders": [
        "https://www.hammerandrails.com/rss/index.xml",      # SB Nation
        "https://purdue.rivals.com/rss",                     # Gold and Black (Rivals)
        "https://247sports.com/college/purdue/Article/rss/", # 247 Purdue
    ],
    "national": [
        "https://www.cbssports.com/college-basketball/teams/PURDUE/purdue-boilermakers/rss/",
        "https://sports.yahoo.com/college-basketball/teams/purdue/news/?format=rss",
        "https://www.espn.com/college-basketball/team/_/id/2509/purdue-boilermakers/rss",
    ],
    "local": [
        # These may include all sports—we filter out football above.
        "https://www.jconline.com/search/?q=Purdue%20basketball&output=rss",
    ],
}

def merge_sources(user_cfg):
    cfg = {"official":[], "insiders":[], "national":[], "local":[]}
    for k in cfg.keys():
        seen=set()
        for u in (user_cfg or {}).get(k, []):
            if u and u not in seen:
                cfg[k].append(u); seen.add(u)
        for u in FALLBACK.get(k, []):
            if u and u not in seen:
                cfg[k].append(u); seen.add(u)
    return cfg

# ----------------- main -----------------
def main():
    user_cfg = load_json(SRC_PATH, {})  # optional
    cfg = merge_sources(user_cfg)

    buckets = [(tier, urls) for tier, urls in cfg.items()]

    raw=[]
    for tier, urls in buckets:
        for u in urls:
            raw.extend(fetch_feed(u, tier))

    # Filter to Purdue MBB only; dedupe; pick 10 newest
    filtered = [it for it in raw if looks_basketball(it)]
    items = uniq(filtered)[:10]

    save_json(OUT_PATH, {"updated": int(time.time()*1000), "items": items})
    print(f"[collect] wrote {OUT_PATH} with {len(items)} Purdue MBB items (<=10)")

if __name__ == "__main__":
    main()