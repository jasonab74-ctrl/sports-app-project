#!/usr/bin/env python3
"""
Team Hub Pro — Feed Collector (YouTube-aware)
Reads static/sources.json, fetches RSS/Atom feeds, filters for Purdue terms,
and writes static/teams/purdue-mbb/items.json with videoId/duration for videos.

Run locally:  python tools/collect.py
"""

import json, re
from datetime import datetime
from pathlib import Path

import feedparser
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "static" / "sources.json"
OUT_FILE = ROOT / "static" / "teams" / "purdue-mbb" / "items.json"
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# ---------- helpers ----------

def clean_html(text: str) -> str:
    if not text: return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)

def iso_date(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                dt = datetime(*val[:6])
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
    # fallback: today UTC
    return datetime.utcnow().strftime("%Y-%m-%d")

YT_ID_PAT = re.compile(r"(?:v=|/shorts/|youtu\.be/)([A-Za-z0-9_-]{6,})")

def extract_video_id(entry) -> str | None:
    # Common fields in YouTube feeds via feedparser
    for key in ("yt_videoid", "yt_video_id", "yt:videoId"):
        vid = entry.get(key)
        if vid: return str(vid)
    # Some feeds put it in 'id' like 'yt:video:ID'
    e_id = entry.get("id") or ""
    m = re.search(r"yt:video:([A-Za-z0-9_-]+)", e_id)
    if m: return m.group(1)
    # Last resort: parse link
    link = entry.get("link") or ""
    m = YT_ID_PAT.search(link)
    if m: return m.group(1)
    return None

def extract_media_duration(entry) -> int | None:
    # feedparser maps media:content@duration to 'media_content'[{'duration': seconds}] sometimes
    try:
        if "media_content" in entry and isinstance(entry["media_content"], list):
            dur = entry["media_content"][0].get("duration")
            if dur is not None:
                return int(float(dur))
    except Exception:
        pass
    # Some feeds expose 'media_duration'
    dur = entry.get("media_duration")
    if dur is not None:
        try:
            return int(float(dur))
        except Exception:
            return None
    return None

def first_image(entry) -> str | None:
    # media:thumbnail or media:content
    thumbs = entry.get("media_thumbnail") or []
    if isinstance(thumbs, list) and thumbs:
        url = thumbs[0].get("url")
        if url: return url
    media = entry.get("media_content") or []
    if isinstance(media, list) and media:
        url = media[0].get("url")
        if url and (url.startswith("http://") or url.startswith("https://")):
            return url
    # parse from HTML
    summary = entry.get("summary") or entry.get("content", [{}])[0].get("value", "")
    if summary:
        m = re.search(r'src="([^"]+)"', summary)
        if m: return m.group(1)
    return None

def trust_for(name: str) -> str:
    if any(k in name for k in ("Purdue", "Athletics", "BTN")):
        return "official"
    if any(k in name for k in ("Rivals","247","Journal","Hammer","Gold and Black")):
        return "insider"
    return "national"

def include_item(title: str, summary: str, keywords: list[str], force: bool) -> bool:
    if force: return True
    hay = f"{title} {summary}".lower()
    return any(k in hay for k in keywords)

# ---------- main ----------

def collect():
    cfg = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    sources = cfg.get("sources", [])
    keywords = [k.lower() for k in cfg.get("keywords", [])]

    items = []
    for s in sources:
        url = s.get("url")
        if not url: continue
        sname = s.get("name", "Source")
        stype = s.get("type", "news")
        trust = s.get("trust") or trust_for(sname)

        feed = feedparser.parse(url)
        for e in feed.entries[:25]:
            title = (e.get("title") or "").strip()
            summary = clean_html(e.get("summary"))
            date = iso_date(e)
            link = e.get("link") or ""
            force_include = (trust == "official")

            # Filter only Purdue-relevant content for non-official news
            if stype == "news" and not include_item(title, summary, keywords, force_include):
                continue

            image = first_image(e)
            item = {
                "type": "video" if stype == "video" else "news",
                "source": sname,
                "trust": trust,
                "title": title,
                "link": link,
                "date": date,
                "summary": summary[:280],
                "image": image
            }

            if stype == "video":
                vid = extract_video_id(e)
                dur = extract_media_duration(e)
                if vid and not image:
                    # Fallback to standard YouTube thumbnail
                    image = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                    item["image"] = image
                if vid:
                    item["videoId"] = vid
                if dur is not None:
                    item["duration"] = dur

            items.append(item)

    # Dedup by (title, source), newest first
    seen = set()
    out = []
    for it in items:
        key = (it["title"], it["source"])
        if key in seen: continue
        seen.add(key)
        out.append(it)

    out.sort(key=lambda x: x.get("date",""), reverse=True)
    OUT_FILE.write_text(json.dumps({"items": out[:80]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out[:80])} items -> {OUT_FILE}")

if __name__ == "__main__":
    collect()
