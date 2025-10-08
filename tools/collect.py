#!/usr/bin/env python3
# tools/collect.py
#
# Build a Purdue *Men's Basketball only* news file from mixed feeds.
# Keeps all OFFICIAL + INSIDERS if they look like MBB, and for NATIONAL/LOCAL
# keeps only items that clearly reference Purdue MBB (title/summary/link).
#
# Output -> static/data/news.json

import os, re, json, time, hashlib, html
from urllib.parse import urlparse
import feedparser

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "static", "data")
SRC_PATH = os.path.join(DATA_DIR, "sources.json")
OUT_PATH = os.path.join(DATA_DIR, "news.json")

# ---- Purdue MBB keyword model ---------------------------------------------
MBB_POSITIVE = [
    # general
    r"\bmen'?s?\s+basketball\b", r"\bmbb\b", r"\bbasketball\b", r"\bhoops?\b",
    r"\bpaint crew\b", r"\bmackey\s+arena\b",
    # coaches
    r"\bmatt\s+painter\b",
    # players (keep a few high-signal current/recent names; extend as needed)
    r"\bzach\s+edey\b", r"\bbraden\s+smith\b", r"\bfletcher\s+loyer\b",
    r"\bcaleb\s+furst\b", r"\bcarsen\s+edwards\b", r"\bjaden\s+ivey\b",
    # opponents often seen in MBB context
    r"\bbig\s+ten\b", r"\bncaa\b", r"\bmarch\s+madness\b",
    r"\bexhibition\b", r"\bregular\s+season\b", r"\btournament\b",
]

# Terms that strongly indicate *football* (to suppress)
FOOTBALL_NEG = [
    r"\bfootball\b", r"\bfball\b", r"\bqb\b", r"\bquarterback\b", r"\brunning\s*back\b",
    r"\bwide\s*receiver\b", r"\boffensive\s*line\b", r"\bdefensive\s*line\b",
    r"\bcoach\s+ryan\s+walters\b", r"\bwalters\b",
    r"\bhudson\s+card\b", r"\bgridiron\b",
    r"\bkinnick\b", r"\bross-ade\b",
]

# Purdue identity (must be present somewhere)
PURDUE_CORE = [r"\bpurdue\b", r"\bboilermakers?\b", r"\bwest\s+lafayette\b"]

def compile_list(rx_list):
    return [re.compile(rx, re.I) for rx in rx_list]

RX_MBB = compile_list(MBB_POSITIVE)
RX_FB  = compile_list(FOOTBALL_NEG)
RX_PU  = compile_list(PURDUE_CORE)

# Path hints that usually mean basketball
PATH_HINTS = [
    "/mbb", "/m-basketball", "/mens-basketball", "/men-basketball",
    "/basketball/", "/college-basketball/", "/ncaa-basketball/"
]

# ---------------------------------------------------------------------------

def load_json(p, d=None):
    if not os.path.exists(p): return d
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def domain(u):
    try: return urlparse(u).hostname or ""
    except: return ""

def clean_text(s):
    if not s: return ""
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def hash_id(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def when_ts(entry):
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        if entry.get(k):
            return int(time.mktime(entry[k])) * 1000
    return int(time.time() * 1000)

def first_image(entry):
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    for m in media:
        if m.get("url"): return m["url"]
    val = entry.get("summary")
    if isinstance(val, list) and val:
        val = val[0].get("value")
    if isinstance(val, str):
        m = re.search(r'<img [^>]*src=["\']([^"\']+)["\']', val, flags=re.I)
        if m: return m.group(1)
    return None

def fetch_feed(url, tier):
    try:
        fp = feedparser.parse(url)
    except Exception:
        return []
    items = []
    for e in fp.entries:
        link = e.get("link") or ""
        title = clean_text(e.get("title"))
        summary = clean_text(
            e.get("summary") or (e.get("content",[{}])[0].get("value") if e.get("content") else "")
        )
        src = domain(link).replace("www.","") or domain(fp.href or url)
        ts = when_ts(e)
        img = first_image(e)
        items.append({
            "id": hash_id(link or title),
            "title": title,
            "summary": summary,
            "link": link,
            "source": src,
            "tier": tier,
            "type": "article",
            "ts": ts,
            "image": img,
            "paywall": False
        })
    return items

def uniq(items):
    seen=set(); out=[]
    for it in sorted(items, key=lambda x: x["ts"], reverse=True):
        key=(it["title"], it["link"])
        if key in seen: continue
        seen.add(key); out.append(it)
    return out

# ---- filtering -------------------------------------------------------------
def has_any(regexes, text):
    return any(r.search(text) for r in regexes)

def looks_basketball(item):
    blob = " ".join([item.get("title",""), item.get("summary",""), item.get("link",""), item.get("source","")]).lower()
    # strong path hints
    path = urlparse(item.get("link","")).path.lower()
    if any(h in path for h in PATH_HINTS):
        return True
    # must look like Purdue, then MBB, and not football
    if not has_any(RX_PU, blob):
        # allow official domains (purduesports.com) to pass Purdue check
        if "purduesports.com" not in (item.get("source","") or ""):
            return False
    if has_any(RX_FB, blob):
        # allow if it *also* clearly says basketball/mbb (rare mixed posts)
        return has_any(RX_MBB, blob)
    return has_any(RX_MBB, blob)

def is_relevant(item, tier):
    # For all tiers, we require MBB-ness
    return looks_basketball(item)

# ---------------------------------------------------------------------------

def main():
    cfg = load_json(SRC_PATH, {})
    if not cfg:
        raise SystemExit("missing static/data/sources.json")

    buckets = [
        ("official", cfg.get("official",[])),
        ("insiders", cfg.get("insiders",[])),
        ("national", cfg.get("national",[])),
        ("local", cfg.get("local",[])),
    ]

    raw=[]
    for tier, urls in buckets:
        for u in urls:
            raw.extend(fetch_feed(u, tier))

    # MBB-only filter
    filtered = [it for it in raw if is_relevant(it, it["tier"])]

    # dedupe + cap
    limit = max(20, int(cfg.get("min_items", 24)))
    items = uniq(filtered)[:limit]

    save_json(OUT_PATH, {"updated": int(time.time()*1000), "items": items})
    print(f"[collect] wrote {OUT_PATH} with {len(items)} MBB items")

if __name__ == "__main__":
    main()