#!/usr/bin/env python3
# tools/collect.py
#
# Build a Purdue-focused news file from mixed feeds.
# Keeps all OFFICIAL + INSIDERS. For NATIONAL/LOCAL, only keep
# items that *mention Purdue* in title/summary/link.
#
# Output -> static/data/news.json

import os, re, json, time, hashlib, datetime, html
from urllib.parse import urlparse
import feedparser, requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "static", "data")
SRC_PATH = os.path.join(DATA_DIR, "sources.json")
OUT_PATH = os.path.join(DATA_DIR, "news.json")

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
    # favor published_parsed → updated_parsed → now
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        if entry.get(k):
            return int(time.mktime(entry[k])) * 1000
    return int(time.time() * 1000)

def first_image(entry):
    # media:content / media:thumbnail / content HTML
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    for m in media:
        if m.get("url"): return m["url"]
    for k in ("summary", "content"):
        val = entry.get(k)
        if isinstance(val, list) and val:
            val = val[0].get("value")
        if isinstance(val, str):
            m = re.search(r'<img [^>]*src=["\']([^"\']+)["\']', val, flags=re.I)
            if m: return m.group(1)
    return None

def is_relevant(item, cfg):
    # Always keep official + insiders
    if item["tier"] in ("official", "insiders"):
        return True
    # For national/local: keep only if Purdue-related
    text = " ".join([item.get("title",""), item.get("summary",""), item.get("link","")]).lower()
    if any(kw.lower() in text for kw in cfg.get("team_keywords", [])):
        return True
    # Also allow explicit whitelisted domains
    host = domain(item.get("link","")).lower()
    if host in (d.lower() for d in cfg.get("allow_domains", [])):
        return True
    return False

def fetch_feed(url, tier):
    try:
        fp = feedparser.parse(url)
    except Exception:
        return []
    items = []
    for e in fp.entries:
        link = e.get("link") or ""
        title = clean_text(e.get("title"))
        summary = clean_text( (e.get("summary") or (e.get("content",[{}])[0].get("value") if e.get("content") else "")) )
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

def unique_by_link(items):
    seen = set(); out = []
    for it in sorted(items, key=lambda x: x["ts"], reverse=True):
        key = (it["title"], it["link"])
        if key in seen: continue
        seen.add(key); out.append(it)
    return out

def main():
    cfg = load_json(SRC_PATH, {})
    if not cfg:
        raise SystemExit("missing sources.json")

    buckets = [
        ("official", cfg.get("official",[])),
        ("insiders", cfg.get("insiders",[])),
        ("national", cfg.get("national",[])),
        ("local", cfg.get("local",[]))
    ]

    all_items = []
    for tier, urls in buckets:
        for u in urls:
            all_items.extend(fetch_feed(u, tier))

    # Purdue-filter (keep official/insiders; filter national/local)
    filtered = [it for it in all_items if is_relevant(it, cfg)]

    # Trim and dedupe
    limit = max(20, int(cfg.get("min_items", 24)))
    items = unique_by_link(filtered)[: limit]

    out = {
        "updated": int(time.time() * 1000),
        "items": items
    }
    save_json(OUT_PATH, out)
    print(f"[collect] wrote {OUT_PATH} with {len(items)} items")

if __name__ == "__main__":
    main()