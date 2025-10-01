#!/usr/bin/env python3
"""
Collects news/video items for each team defined in static/sources.json and writes
static/teams/<slug>/items.json

Improvements:
- OpenGraph fallback (grabs og:image if feed doesn't expose an image)
- Title de-duplication across feeds (drops near-duplicates)
- Gentle hardening (timeouts, user-agent, keeps newest items)
"""

from __future__ import annotations
import os, re, json, time, argparse, datetime as dt
from urllib.parse import urlparse, urljoin

import requests
import feedparser
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(__file__))  # repo root from tools/
SRC_PATH = os.path.join(ROOT, "static", "sources.json")
OUT_ROOT = os.path.join(ROOT, "static", "teams")

UA = "SportsAppCollector/1.1 (+https://github.com/)"
TIMEOUT = 20

def fetch(url: str) -> bytes:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content

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

IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)

def extract_open_graph(url: str) -> str:
    """Fetches the page and returns og:image if present."""
    try:
        html = fetch(url)
        soup = BeautifulSoup(html, "lxml")
        og = soup.find("meta", property="og:image")
        return (og.get("content") or "").strip() if og else ""
    except Exception:
        return ""

def extract_image(entry, base_link: str | None) -> str:
    # media:thumbnail / media:content / image fields
    for key in ("media_thumbnail", "media_content", "image"):
        val = entry.get(key)
        if isinstance(val, list) and val:
            url = val[0].get("url")
            if url:
                return url
        if isinstance(val, dict):
            url = val.get("url")
            if url:
                return url
        if isinstance(val, str) and val:
            return val

    # content / summary <img>
    html = ""
    if "content" in entry and entry["content"]:
        html = entry["content"][0].get("value") or ""
    elif "summary" in entry:
        html = entry.get("summary", "") or ""

    m = IMG_RE.search(html or "")
    if m:
        src = m.group(1)
        if base_link and src.startswith("/"):
            try:
                return urljoin(base_link, src)
            except Exception:
                pass
        return src

    # fallback: OpenGraph from article page
    if base_link:
        og = extract_open_graph(base_link)
        if og:
            return og

    return ""

def is_video(entry, link: str) -> bool:
    if "yt_videoid" in entry or "media_player" in entry:
        return True
    if "enclosures" in entry:
        for enc in entry["enclosures"]:
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

def normalize_feed_items(feed_url: str) -> list[dict]:
    data = fetch(feed_url)
    parsed = feedparser.parse(data)
    items = []
    for e in parsed.entries:
        link = e.get("link") or ""
        if not link:
            continue
        title = e.get("title") or ""
        pub = e.get("published") or e.get("updated") or None
        date_iso = to_iso(pub)
        img = extract_image(e, link)
        items.append({
            "title": title,
            "url": link,
            "image": img,
            "thumbnail": img,
            "source": source_name(link),
            "date": date_iso,
            "tag": "Video" if is_video(e, link) else "News",
            "is_video": is_video(e, link)
        })
    return items

def youtube_feed(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

def norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r'&[#0-9a-z]+;', ' ', t)
    t = re.sub(r'[^a-z0-9 ]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:100]

def collect_for_team(slug: str, cfg: dict) -> dict:
    max_items = int(cfg.get("max_items", 60))
    items: list[dict] = []

    # RSS feeds
    for url in cfg.get("feeds", []):
        try:
            items.extend(normalize_feed_items(url))
        except Exception as ex:
            print(f"[warn] {slug} feed failed: {url} -> {ex}")

    # YouTube channels via RSS
    for cid in cfg.get("youtube_channels", []):
        try:
            yitems = normalize_feed_items(youtube_feed(cid))
            for it in yitems:
                it["is_video"] = True
                it["tag"] = "Video"
            items.extend(yitems)
        except Exception as ex:
            print(f"[warn] {slug} youtube failed: {cid} -> {ex}")

    # Sort newest first
    items.sort(key=lambda x: x.get("date",""), reverse=True)

    # De-duplicate by URL and fuzzy title
    seen_urls = set()
    seen_titles = set()
    dedup = []
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
