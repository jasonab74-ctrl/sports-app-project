#!/usr/bin/env python3
"""Team Hub Pro — Feed Collector
Reads static/sources.json, fetches RSS/Atom feeds, filters for Purdue terms,
and writes static/teams/purdue-mbb/items.json.
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
    return datetime.utcnow().strftime("%Y-%m-%d")

def first_image(entry) -> str | None:
    media = entry.get("media_content") or []
    if isinstance(media, list) and media:
        url = media[0].get("url")
        if url: return url
    thumbs = entry.get("media_thumbnail") or []
    if isinstance(thumbs, list) and thumbs:
        url = thumbs[0].get("url")
        if url: return url
    summary = entry.get("summary") or entry.get("content", [{}])[0].get("value", "")
    if summary:
        m = re.search(r'src="([^"]+)"', summary)
        if m: return m.group(1)
    return None

def trust_for(name: str) -> str:
    if "Purdue" in name or "Athletics" in name or "BTN" in name: return "official"
    if any(k in name for k in ("Rivals","247","Journal","Hammer")): return "insider"
    return "national"

def collect():
    data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    sources = data.get("sources", [])
    keywords = [k.lower() for k in data.get("keywords", [])]
    items = []

    def include_item(title, summary):
        hay = f"{title} {summary}".lower()
        return any(k in hay for k in keywords)

    for s in sources:
        url = s.get("url"); stype = s.get("type","news"); sname = s.get("name","Source")
        if not url: continue
        feed = feedparser.parse(url)
        for e in feed.entries[:25]:
            title = e.get("title","").strip()
            summary = clean_html(e.get("summary",""))
            date = iso_date(e)
            link = e.get("link","")
            img = first_image(e)
            trust = s.get("trust") or trust_for(sname)
            if stype == "news" and trust != "official" and not include_item(title, summary):
                continue
            items.append({
                "type": "video" if stype == "video" else "news",
                "source": sname,
                "trust": trust,
                "title": title,
                "link": link,
                "date": date,
                "summary": summary[:280],
                "image": img
            })
    # Dedup and sort
    seen=set(); out=[]
    for it in items:
        key=(it["title"], it["source"])
        if key in seen: continue
        seen.add(key); out.append(it)
    out.sort(key=lambda x: x.get("date",""), reverse=True)
    OUT_FILE.write_text(json.dumps({"items": out[:80]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out[:80])} items -> {OUT_FILE}")

if __name__ == "__main__":
    collect()
