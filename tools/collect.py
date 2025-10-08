#!/usr/bin/env python3
# tools/collect.py
#
# Purdue *Men's Basketball only* news builder with image fallback.
# Output -> static/data/news.json

import os, re, json, time, hashlib, html
from urllib.parse import urlparse
import feedparser, requests

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "static", "data")
SRC_PATH = os.path.join(DATA_DIR, "sources.json")
OUT_PATH = os.path.join(DATA_DIR, "news.json")

# ---- Purdue MBB keyword model ---------------------------------------------
MBB_POSITIVE = [
    r"\bmen'?s?\s+basketball\b", r"\bmbb\b", r"\bbasketball\b", r"\bhoops?\b",
    r"\bpaint crew\b", r"\bmackey\s+arena\b",
    r"\bmatt\s+painter\b",
    r"\bzach\s+edey\b", r"\bbraden\s+smith\b", r"\bfletcher\s+loyer\b", r"\bcaleb\s+furst\b",
    r"\bbig\s+ten\b", r"\bncaa\b", r"\bmarch\s+madness\b", r"\bexhibition\b", r"\bregular\s+season\b", r"\btournament\b",
]
FOOTBALL_NEG = [
    r"\bfootball\b", r"\bfball\b", r"\bqb\b", r"\bquarterback\b", r"\brunning\s*back\b",
    r"\bwide\s*receiver\b", r"\boffensive\s*line\b", r"\bdefensive\s*line\b",
    r"\bcoach\s+ryan\s+walters\b", r"\bwalters\b", r"\bhudson\s+card\b", r"\bgridiron\b", r"\bross-ade\b",
]
PURDUE_CORE = [r"\bpurdue\b", r"\bboilermakers?\b", r"\bwest\s+lafayette\b"]

def compile_list(rx_list): return [re.compile(rx, re.I) for rx in rx_list]
RX_MBB = compile_list(MBB_POSITIVE)
RX_FB  = compile_list(FOOTBALL_NEG)
RX_PU  = compile_list(PURDUE_CORE)

PATH_HINTS = [
    "/mbb", "/m-basketball", "/mens-basketball", "/men-basketball",
    "/basketball/", "/college-basketball/", "/ncaa-basketball/"
]

def load_json(p, d=None):
    if not os.path.exists(p): return d
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def domain(u):
    try: return (urlparse(u).hostname or "").replace("www.","")
    except: return ""

def clean_text(s):
    if not s: return ""
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def hash_id(s): return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]

def when_ts(entry):
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        if entry.get(k):
            return int(time.mktime(entry[k])) * 1000
    return int(time.time() * 1000)

IMG_RX = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
def image_from_html(html_str):
    if not isinstance(html_str, str): return None
    m = IMG_RX.search(html_str)
    return m.group(1) if m else None

def first_image(entry):
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    for m in media:
        url = m.get("url")
        if url: return url
    if entry.get("content"):
        for c in entry["content"]:
            url = image_from_html(c.get("value") or "")
            if url: return url
    url = image_from_html(entry.get("summary") or "")
    if url: return url
    sd = entry.get("summary_detail") or {}
    if sd.get("type") and "html" in sd.get("type"):
        url = image_from_html(sd.get("value") or "")
        if url: return url
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
    items = []
    for e in fp.entries:
        link = e.get("link") or ""
        title = clean_text(e.get("title"))
        summary_txt = clean_text(
            e.get("summary") or (e.get("content",[{}])[0].get("value") if e.get("content") else "")
        )
        src = domain(link) or domain(fp.href or url)
        ts = when_ts(e)
        img = first_image(e) or (og_image(link) if link else None)
        items.append({
            "id": hash_id(link or title),
            "title": title,
            "summary": summary_txt,
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

def has_any(rx_list, text): return any(rx.search(text) for rx in rx_list)

def looks_basketball(item):
    blob = " ".join([item.get("title",""), item.get("summary",""), item.get("link",""), item.get("source","")]).lower()
    path = urlparse(item.get("link","")).path.lower()
    if any(h in path for h in PATH_HINTS):
        pass
    else:
        if not has_any(RX_PU, blob) and "purduesports.com" not in (item.get("source") or ""):
            return False
        if has_any(RX_FB, blob) and not has_any(RX_MBB, blob):
            return False
        if not has_any(RX_MBB, blob):
            return False
    return True

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
    for _, urls in buckets:
        for u in urls:
            raw.extend(fetch_feed(u, _))

    filtered = [it for it in raw if looks_basketball(it)]
    items = uniq(filtered)[:10]  # <<<<<< cap to 10

    save_json(OUT_PATH, {"updated": int(time.time()*1000), "items": items})
    print(f"[collect] wrote {OUT_PATH} with {len(items)} MBB items (<=10)")
if __name__ == "__main__":
    main()