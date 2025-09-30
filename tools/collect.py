#!/usr/bin/env python3
import feedparser, json, re, requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[1]
SOURCES_FILE = BASE_DIR / "static" / "sources.json"
OUTPUT_FILE = BASE_DIR / "static" / "teams" / "purdue-mbb" / "items.json"

def clean_html(text):
    return re.sub("<[^<]+?>", "", text or "")

def fetch_youtube_thumb(link):
    # Extract video ID for YouTube links
    match = re.search(r"v=([a-zA-Z0-9_-]{11})", link)
    return f"https://img.youtube.com/vi/{match.group(1)}/hqdefault.jpg" if match else None

def parse_feed(source):
    print(f"Fetching from: {source['name']}")
    feed = feedparser.parse(source['url'])
    results = []
    for entry in feed.entries[:15]:
        item = {
            "type": source["type"],
            "source": source["name"],
            "trust": source["trust"],
            "title": entry.get("title", "Untitled"),
            "link": entry.get("link", "#"),
            "date": entry.get("published", "")[:10],
            "summary": clean_html(entry.get("summary", "")),
            "image": None
        }

        # Try to get a thumbnail
        if source["type"] == "video":
            thumb = fetch_youtube_thumb(item["link"])
            item["image"] = thumb or "static/placeholder.jpg"
        else:
            # Attempt to get image from content if available
            if "media_content" in entry and len(entry.media_content) > 0:
                item["image"] = entry.media_content[0].get("url")
            elif "summary" in entry:
                soup = BeautifulSoup(entry.summary, "html.parser")
                img_tag = soup.find("img")
                if img_tag and img_tag.get("src"):
                    item["image"] = img_tag["src"]

        results.append(item)
    return results

def main():
    print("📡 Starting feed collection...")
    with open(SOURCES_FILE) as f:
        sources = json.load(f)["sources"]

    all_items = []
    for src in sources:
        try:
            all_items.extend(parse_feed(src))
        except Exception as e:
            print(f"⚠️ Error fetching {src['name']}: {e}")

    # Sort items by date (newest first)
    all_items = sorted(all_items, key=lambda x: x.get("date", ""), reverse=True)

    data = {"items": all_items[:50]}  # limit to 50 total
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Wrote {len(data['items'])} items to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()