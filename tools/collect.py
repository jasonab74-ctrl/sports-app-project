#!/usr/bin/env python3
import json, re
from pathlib import Path
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parents[1]
SOURCES_PATH = BASE / "static" / "sources.json"
OUTPUT_PATH = BASE / "static" / "teams" / "purdue-mbb" / "items.json"

def clean_html(txt):
    return re.sub(r"<[^>]+>", "", txt or "")

def parse_date(entry):
    # Prefer parsed published date, fall back to today
    try:
      if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6])
        return dt.strftime("%Y-%m-%d")
    except Exception:
      pass
    return datetime.utcnow().strftime("%Y-%m-%d")

def youtube_thumb(url):
    m = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", url)
    return f"https://img.youtube.com/vi/{m.group(1)}/hqdefault.jpg" if m else None

def entry_image(entry):
    # Try media content, then first <img> in summary
    media = getattr(entry, "media_content", None)
    if media and isinstance(media, list) and media:
        u = media[0].get("url")
        if u: return u
    summ = getattr(entry, "summary", "") or ""
    try:
        soup = BeautifulSoup(summ, "html.parser")
        tag = soup.find("img")
        if tag and tag.get("src"): return tag["src"]
    except Exception:
        pass
    return None

def parse_feed(src):
    print(f"Fetching: {src['name']} ({src['type']})")
    d = feedparser.parse(src["url"])
    out = []
    for e in d.entries[:25]:
        item = {
            "type": "video" if src["type"] == "video" else "news",
            "source": src["name"],
            "trust": src.get("trust", "national"),
            "title": e.get("title", "").strip(),
            "link": e.get("link", "").strip(),
            "date": parse_date(e),
            "summary": clean_html(e.get("summary", ""))[:240],
            "image": None
        }
        if src["type"] == "video":
            item["image"] = youtube_thumb(item["link"]) or entry_image(e)
        else:
            item["image"] = entry_image(e)
        out.append(item)
    return out

def main():
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        sources = json.load(f)["sources"]

    all_items = []
    for src in sources:
        try:
            all_items += parse_feed(src)
        except Exception as ex:
            print("WARN:", src["name"], ex)

    # sort newest first, limit
    all_items.sort(key=lambda x: x.get("date",""), reverse=True)
    data = {"items": all_items[:50]}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(data['items'])} to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()