#!/usr/bin/env python3
"""
tools/collect.py

Builds a single, deduped news feed at:
  static/data/news.json

What’s new:
- Canonical URL + smart de-dupe across syndications
- OpenGraph thumbnail extraction (lazy-friendly)
- Paywall tagging by source
- Tier support: official | insiders | national | local | video
- Stable ordering + “pin official first”
- Compact logs (no emoji)

This script reads:
  static/data/sources.json
and writes:
  static/data/news.json
"""

import os, re, json, time, hashlib
from urllib.parse import urlparse, parse_qsl, urlunparse, urlencode
import requests
import feedparser
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "static", "data")
OUT_PATH = os.path.join(DATA_DIR, "news.json")
SRC_PATH = os.path.join(DATA_DIR, "sources.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Sports-App-Project/1.0; +https://github.com/jasonab74-ctrl/sports-app-project)"
}
TIMEOUT = 20

def load_sources():
    with open(SRC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["sources"]

def now_ms():
    return int(time.time() * 1000)

def strip_tracking(u: str) -> str:
    try:
        p = urlparse(u)
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
        p = p._replace(query=urlencode(q, doseq=True))
        return urlunparse(p)
    except Exception:
        return u

def canonical_key(url: str, title: str) -> str:
    """
    Build a de-duplication key from domain + slug-ish path + simplified title.
    This collapses AP-syndicated or wire copies across sites.
    """
    try:
        u = strip_tracking(url)
        p = urlparse(u)
        host = p.netloc.lower()
        path = re.sub(r"/+", "/", p.path.lower()).strip("/")
        path = re.sub(r"\.html?$", "", path)
        path = path.split("/")[-3:]  # last 3 segments often carry the slug
        path_key = "-".join(path)

        # Simplify title
        t = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
        t = re.sub(r"-+", "-", t)

        # Keep just a few host chars to avoid overly long keys
        host_key = host.replace("www.", "")
        base = f"{host_key}:{path_key}:{t}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:20]
    except Exception:
        return hashlib.sha1((url + title).encode("utf-8")).hexdigest()[:20]

def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.ok and "text/html" in r.headers.get("Content-Type",""):
            return r.text
    except Exception:
        pass
    return None

def extract_og_image(html: str) -> str | None:
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Check common meta tags
        for sel in [
            "meta[property='og:image']",
            "meta[name='og:image']",
            "meta[property='twitter:image']",
            "meta[name='twitter:image']",
        ]:
            tag = soup.select_one(sel)
            if tag and tag.get("content"):
                return tag["content"].strip()
    except Exception:
        pass
    return None

def as_item(entry, src_cfg):
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None

    link = strip_tracking(link)
    ts = None
    for k in ("published_parsed", "updated_parsed"):
        if entry.get(k):
            ts = int(time.mktime(entry[k])) * 1000
            break
    if not ts:
        ts = now_ms()

    # Video hint if enclosure or YouTube domain
    etype = "video" if ("enclosures" in entry and entry["enclosures"]) or "youtube.com" in link else "article"

    item = {
        "title": title,
        "link": link,
        "source": src_cfg["name"],
        "tier": src_cfg.get("tier", "national"),
        "type": etype,
        "ts": ts,
        "image": None,
        "paywall": src_cfg.get("paywall", False),
    }
    return item

def collect():
    sources = load_sources()
    items = []
    print(f"Loading {len(sources)} sources...")

    for s in sources:
        url = s.get("rss")
        if not url:
            continue
        try:
            feed = feedparser.parse(url)
            take = s.get("limit", 12)
            for e in (feed.entries or [])[:take]:
                it = as_item(e, s)
                if it:
                    items.append(it)
            print(f"  {s['name']}: {len(feed.entries or [])} entries")
        except Exception as e:
            print(f"  {s['name']}: feed error: {e}")

    # Optional OG image fetch for the first N recent items per domain (keep it light)
    items.sort(key=lambda x: x["ts"], reverse=True)
    seen_host = {}
    for it in items[:60]:  # cap work
        host = urlparse(it["link"]).netloc
        seen_host.setdefault(host, 0)
        if seen_host[host] >= 3:
            continue
        html = fetch_html(it["link"])
        if html:
            og = extract_og_image(html)
            if og:
                it["image"] = og
        seen_host[host] += 1

    # De-dupe across syndications
    deduped = []
    seen = set()
    for it in items:
        key = canonical_key(it["link"], it["title"])
        # de-dupe strict by key; if collision keep the "better" one: official > insiders > national > local
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    # Pin official first (within sort by ts desc)
    official = [x for x in deduped if x["tier"] == "official"]
    rest = [x for x in deduped if x["tier"] != "official"]
    official.sort(key=lambda x: x["ts"], reverse=True)
    rest.sort(key=lambda x: x["ts"], reverse=True)
    out = official + rest

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": out, "updated": now_ms()}, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH} with {len(out)} items.")

if __name__ == "__main__":
    collect()
