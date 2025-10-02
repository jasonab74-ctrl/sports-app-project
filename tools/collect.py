#!/usr/bin/env python3
"""
Collector: builds static/teams/<slug>/items.json from static/sources.json

Upgrades vs prior:
- Retries with backoff, sane timeouts & UA
- Per-source cap + global cap + max age filter
- Stronger dedupe (URL + fuzzy title)
- Better image picking: media tags -> <img> -> OpenGraph og:image
- UTM/tracking param stripping
- Lightweight language/garbage filter
"""

from __future__ import annotations
import os, re, json, time, math, hashlib, datetime as dt
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin

import requests
import feedparser
from bs4 import BeautifulSoup

# Paths
ROOT = os.path.dirname(os.path.dirname(__file__))  # repo root from tools/
SRC_PATH = os.path.join(ROOT, "static", "sources.json")
OUT_ROOT = os.path.join(ROOT, "static", "teams")

# HTTP
UA = "SportsAppCollector/1.2 (+https://github.com/)"
TIMEOUT = 18
RETRIES = 2
BACKOFF = 1.6

# Regex
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
WS_RE = re.compile(r'\s+')

def clean_url(u: str) -> str:
    """Strip tracking params (utm_*, fbclid, gclid, etc.)."""
    try:
        p = urlparse(u)
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not (k.lower().startswith("utm_") or k.lower() in {"fbclid","gclid","mc_cid","mc_eid","cmpid"})]
        return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, doseq=True), ""))  # drop fragment
    except Exception:
        return u

def fetch(url: str) -> bytes:
    last = None
    for i in range(RETRIES + 1):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last = e
            if i < RETRIES:
                time.sleep((BACKOFF ** i) + (0.05 * i))
            else:
                raise last

def to_iso(ts) -> str:
    if ts is None:
        return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    if isinstance(ts, (int, float)):
        return dt.datetime.utcfromtimestamp(ts).replace(microsecond=0).isoformat() + "Z"
    if isinstance(ts, str):
        if re.match(r"^\d{4}-\d{2}-\d{2}T", ts):
            return ts
        try:
            t = feedparser._parse_date(ts)  # type: ignore
            if t:
                return to_iso(time.mktime(t))
        except Exception:
            pass
        return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    try:
        return to_iso(time.mktime(ts))
    except Exception:
        return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def extract_open_graph(url: str) -> str:
    try:
        html = fetch(url)
        soup = BeautifulSoup(html, "lxml")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"].strip()
    except Exception:
        pass
    return ""

def extract_image(entry, base_link: str | None) -> str:
    # media tags first
    for key in ("media_thumbnail", "media_content", "image"):
        val = entry.get(key)
        if isinstance(val, list) and val:
            url = val[0].get("url")
            if url: return url
        if isinstance(val, dict):
            url = val.get("url")
            if url: return url
        if isinstance(val, str) and val:
            return val

    # HTML content/summary <img>
    html = ""
    if entry.get("content"):
        html = entry["content"][0].get("value") or ""
    elif entry.get("summary"):
        html = entry.get("summary") or ""
    m = IMG_RE.search(html or "")
    if m:
        src = m.group(1)
        if base_link and src.startswith("/"):
            try:
                return urljoin(base_link, src)
            except Exception:
                pass
        return src

    # Fallback: OG image
    if base_link:
        og = extract_open_graph(base_link)
        if og:
            return og
    return ""

def is_video(entry, link: str) -> bool:
    if "yt_videoid" in entry or "media_player" in entry:
        return True
    for enc in entry.get("enclosures", []):
        t = (enc.get("type") or "").lower()
        if "video" in t:
            return True
    return "youtube.com" in link or "youtu.be" in link

def source_name(link: str) -> str:
    try:
        host = urlparse(link).netloc or ""
        return host.replace("www.", "")
    except Exception:
        return ""

def norm_title(t: str) -> str:
    t = t or ""
    t = t.lower()
    t = re.sub(r'&[#0-9a-z]+;', ' ', t)  # entities
    t = re.sub(r'[^a-z0-9 ]+', ' ', t)
    t = WS_RE.sub(' ', t).strip()
    return t[:110]

def plausible_language_ok(t: str) -> bool:
    # super-light check to avoid non-English junk: ASCII ratio test
    if not t: return False
    ascii_count = sum(1 for ch in t if ord(ch) < 128)
    return ascii_count / max(1, len(t)) > 0.80

def normalize_entry(e) -> dict | None:
    link = clean_url(e.get("link") or "")
    title = (e.get("title") or "").strip()
    if not (link and title and plausible_language_ok(title)):
        return None
    pub = e.get("published") or e.get("updated") or None
    date_iso = to_iso(pub)
    img = extract_image(e, link)
    video = is_video(e, link)
    return {
        "title": title,
        "url": link,
        "image": img,
        "thumbnail": img,
        "source": source_name(link),
        "date": date_iso,
        "tag": "Video" if video else "News",
        "is_video": video
    }

def normalize_feed_items(feed_url: str, max_per_source: int) -> list[dict]:
    out: list[dict] = []
    data = fetch(feed_url)
    parsed = feedparser.parse(data)
    for e in parsed.entries[: max_per_source * 2]:  # scan a little deeper; we'll cap later
        item = normalize_entry(e)
        if item:
            out.append(item)
    return out[:max_per_source]

def youtube_feed(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

def collect_for_team(slug: str, cfg: dict) -> dict:
    max_items = int(cfg.get("max_items", 60))
    max_per_source = int(cfg.get("max_per_source", 20))
    max_age_days = int(cfg.get("max_age_days", 21))

    items: list[dict] = []

    # RSS feeds
    for url in cfg.get("feeds", []):
        try:
            items.extend(normalize_feed_items(url, max_per_source))
        except Exception as ex:
            print(f"[warn] {slug} feed failed: {url} -> {ex}")

    # YouTube via RSS
    for cid in cfg.get("youtube_channels", []):
        try:
            yitems = normalize_feed_items(youtube_feed(cid), max_per_source // 2 or 5)
            for it in yitems:
                it["is_video"] = True
                it["tag"] = "Video"
            items.extend(yitems)
        except Exception as ex:
            print(f"[warn] {slug} youtube failed: {cid} -> {ex}")

    # Sort newest first
    items.sort(key=lambda x: x.get("date",""), reverse=True)

    # Age filter
    if max_age_days > 0:
        cutoff = dt.datetime.utcnow() - dt.timedelta(days=max_age_days)
        items = [it for it in items if dt.datetime.fromisoformat(it["date"].replace("Z","")) >= cutoff]

    # De-duplicate by URL and fuzzy title
    seen_urls, seen_titles, dedup = set(), set(), []
    for it in items:
        u = it["url"]
        tkey = norm_title(it.get("title",""))
        if u in seen_urls or tkey in seen_titles:
            continue
        seen_urls.add(u); seen_titles.add(tkey)
        dedup.append(it)

    dedup = dedup[:max_items]

    return {
        "generated_at": to_iso(None),
        "count": len(dedup),
        "items": dedup
    }

def main():
    with open(SRC_PATH, "r", encoding="utf-8") as f:
        sources = json.load(f)

    os.makedirs(OUT_ROOT, exist_ok=True)

    for slug, cfg in sources.items():
        print(f"[collect] {slug}")
        out = collect_for_team(slug, cfg)
        out_dir = os.path.join(OUT_ROOT, slug)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "items.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[write] {out_path} ({out['count']} items)")

if __name__ == "__main__":
    main()