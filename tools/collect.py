#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Purdue Men's Basketball Collector (News + Fan Board)
----------------------------------------------------
- Reads sources from static/sources.json
- Builds two outputs:
   1) static/teams/purdue-mbb/items.json  (News articles)
   2) static/teams/purdue-mbb/board.json  (Fan board threads)
- Filters to Purdue men's basketball, dedupes, sorts newest→oldest, caps 20.
"""

import os, json, re, time, html, hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(__file__))
TEAM_DIR = os.path.join(ROOT, "static", "teams", "purdue-mbb")
NEWS_PATH = os.path.join(TEAM_DIR, "items.json")
BOARD_PATH = os.path.join(TEAM_DIR, "board.json")
SRC_PATH = os.path.join(ROOT, "static", "sources.json")

os.makedirs(TEAM_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def clean(text: str) -> str:
    if not text:
        return ""
    txt = html.unescape(text)
    txt = re.sub(r"\s+", " ", BeautifulSoup(txt, "html.parser").get_text()).strip()
    return txt

def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()

def parse_epoch(struct_time) -> int:
    try:
        return int(time.mktime(struct_time))
    except Exception:
        return 0

def make_hash(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""

# ---------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------

NEG = re.compile(r"\b(football|volleyball|wrestling|soccer|softball|baseball|track|tennis|golf|women'?s)\b", re.I)
POS = re.compile(r"\b(purdue|boilermakers?|painter|basketball|mbb|mackey)\b", re.I)

def likely_purdue_mbb(text: str) -> bool:
    t = text.lower()
    return bool(POS.search(t)) and not NEG.search(t)

# ---------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------

session = requests.Session()
session.headers.update({
    "User-Agent": "sports-app-project/1.0 (+https://github.com/jasonab74-ctrl)"
})

# ---------------------------------------------------------------------
# Scrapers
# ---------------------------------------------------------------------

def scrape_on3_news(url: str):
    """On3 Purdue Basketball News."""
    out = []
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Look for article cards and links
        cards = soup.select("article, div.card, a[data-vars-content-type='article']")
        for c in cards:
            a = c.find("a", href=True)
            if not a: 
                continue
            title = clean(a.get_text())
            if not title or len(title) < 10:
                continue
            if not likely_purdue_mbb(title):
                continue
            link = urljoin(url, a["href"])
            # try summary + time
            desc_el = c.find("p") or c.find("div", class_=re.compile("summary|dek|deck|excerpt"))
            summary = clean(desc_el.get_text()) if desc_el else ""
            time_el = c.find("time")
            if time_el and time_el.get("datetime"):
                published = time_el["datetime"]
            else:
                published = now_iso()

            out.append({
                "title": title,
                "summary": summary,
                "url": link,
                "published": published,
                "source": "On3 — Purdue Basketball News"
            })
    except Exception as e:
        print(f"[WARN] On3 news scrape failed: {e}")
    return out

def scrape_on3_board(url: str):
    """On3 Free Board — Boilermaker Men's Basketball (threads)."""
    out = []
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        threads = soup.select("div.structItem--thread")
        for t in threads:
            title_el = t.select_one("div.structItem-title a")
            if not title_el:
                continue
            title = clean(title_el.text)
            href = title_el.get("href") or ""
            if not href:
                continue
            # skip stickies/pagination junk
            if "sticky" in href or "page-" in href:
                continue

            if not likely_purdue_mbb(title):
                continue

            link = urljoin(url, href)
            time_el = t.select_one("time")
            if time_el and time_el.get("datetime"):
                published = time_el["datetime"]
            else:
                published = now_iso()

            out.append({
                "title": title,
                "summary": "Fan discussion thread on On3 Free Board.",
                "url": link,
                "published": published,
                "source": "On3 — Purdue MBB Board"
            })
    except Exception as e:
        print(f"[WARN] On3 board scrape failed: {e}")
    return out

def scrape_generic_html(url: str, source_name: str):
    out = []
    try:
        r = session.get(url, timeout=20)
        if r.status_code >= 400:
            return out
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            title = clean(a.get_text())
            if len(title) < 15:
                continue
            if not likely_purdue_mbb(title):
                continue
            link = urljoin(url, a["href"])
            out.append({
                "title": title,
                "summary": "",
                "url": link,
                "published": now_iso(),
                "source": source_name
            })
    except Exception as e:
        print(f"[WARN] scrape_generic_html({source_name}): {e}")
    return out

def parse_rss(url: str, source_name: str):
    out = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:60]:
            title = clean(e.get("title", ""))
            link = e.get("link", "")
            summary = clean(e.get("summary", "") or e.get("description", ""))
            if not title or not link:
                continue
            if not likely_purdue_mbb(f"{title} {summary}"):
                continue
            pub_ts = 0
            if getattr(e, "published_parsed", None):
                pub_ts = parse_epoch(e.published_parsed)
            elif getattr(e, "updated_parsed", None):
                pub_ts = parse_epoch(e.updated_parsed)
            published = datetime.fromtimestamp(pub_ts or time.time(), tz=timezone.utc).isoformat()
            out.append({
                "title": title,
                "summary": summary,
                "url": link,
                "published": published,
                "source": source_name
            })
    except Exception as e:
        print(f"[WARN] RSS parse failed for {source_name}: {e}")
    return out

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def write_json(path: str, payload: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def main():
    with open(SRC_PATH, "r", encoding="utf-8") as f:
        conf = json.load(f)
    feeds = conf.get("feeds", [])
    limit = int(conf.get("max_items", 20))

    news_items, board_items = [], []
    seen_news, seen_board = set(), set()

    for s in feeds:
        name = s.get("name", "Source")
        url = s.get("url", "")
        stype = s.get("type", "rss")
        kind = s.get("kind", "news")  # "news" or "board"

        items = []
        try:
            if "on3.com/teams/purdue-boilermakers/category/basketball/news" in url:
                items = scrape_on3_news(url)
            elif "on3.com/boards/forums/free-board-boilermaker-mens-basketball" in url:
                items = scrape_on3_board(url)
            elif stype == "rss":
                items = parse_rss(url, name)
            else:
                items = scrape_generic_html(url, name)
        except Exception as e:
            print(f"[WARN] fetch failed for {name}: {e}")
            items = []

        if kind == "board":
            for it in items:
                key = make_hash(it["title"] + it["url"])
                if key in seen_board: 
                    continue
                seen_board.add(key)
                board_items.append(it)
        else:
            for it in items:
                key = make_hash(it["title"] + it["url"])
                if key in seen_news: 
                    continue
                seen_news.add(key)
                news_items.append(it)

    # Sort newest → oldest by published
    def sort_key(x):
        try:
            return datetime.fromisoformat(x["published"]).timestamp()
        except Exception:
            return 0

    news_items.sort(key=sort_key, reverse=True)
    board_items.sort(key=sort_key, reverse=True)

    news_items = news_items[:limit]
    board_items = board_items[:limit]

    # Write outputs
    write_json(NEWS_PATH, {
        "team": "purdue-mbb",
        "generated_at": now_iso(),
        "count": len(news_items),
        "items": news_items
    })
    write_json(BOARD_PATH, {
        "team": "purdue-mbb",
        "generated_at": now_iso(),
        "count": len(board_items),
        "items": board_items
    })

    print(f"Wrote {len(news_items)} news → {NEWS_PATH}")
    print(f"Wrote {len(board_items)} board → {BOARD_PATH}")

if __name__ == "__main__":
    main()