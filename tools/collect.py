#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purdue MBB collector: news + On3 fan board
- Pulls multiple sources, filters to Purdue MBB, dedupes, sorts desc, writes items.json
- Scrapes On3 Free Board (HTML), normalizes relative dates, writes board.json
"""

import os, re, json, time, math, html, hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_ROOT = os.path.normpath(os.path.join(ROOT, ".."))
TEAM_SLUG = "purdue-mbb"
OUT_DIR = os.path.join(SITE_ROOT, "static", "teams", TEAM_SLUG)
os.makedirs(OUT_DIR, exist_ok=True)

TZ = timezone(timedelta(hours=-5))  # ET fallback; timestamps stay ISO with Z

# -------------------------
# Utilities
# -------------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def decode(s: str) -> str:
    return html.unescape((s or "").strip())

def sha(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

def canonical_url(u: str) -> str:
    try:
        p = urlparse(u)
        # drop tracking params
        return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
    except Exception:
        return u

def parse_datetime_guess(entry):
    """
    Robust date resolver: feed published/parsing + relative phrases.
    Returns aware UTC datetime.
    """
    # 1) feed fields
    for key in ("published_parsed", "updated_parsed"):
        dt = getattr(entry, key, None)
        if dt:
            return datetime.fromtimestamp(time.mktime(dt), timezone.utc)
    # 2) dict access
    for key in ("published_parsed", "updated_parsed"):
        dt = entry.get(key)
        if dt:
            return datetime.fromtimestamp(time.mktime(dt), timezone.utc)
    # 3) text fields
    txt = (entry.get("published") or entry.get("updated") or entry.get("date") or "").strip()
    if txt:
        # try multiple known patterns
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%b %d, %Y",
            "%b %d %Y",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(txt, fmt).astimezone(timezone.utc)
            except Exception:
                pass
        # relative e.g. "9 hours ago"
        rel = txt.lower()
        m = re.search(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", rel)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            dt = datetime.now(timezone.utc)
            if unit.startswith("minute"):
                dt -= timedelta(minutes=n)
            elif unit.startswith("hour"):
                dt -= timedelta(hours=n)
            elif unit.startswith("day"):
                dt -= timedelta(days=n)
            elif unit.startswith("week"):
                dt -= timedelta(weeks=n)
            elif unit.startswith("month"):
                dt -= timedelta(days=30*n)
            return dt
        # absolute short like 10/27/25
        m2 = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", txt)
        if m2:
            mm, dd, yy = m2.groups()
            yy = int(yy)
            if yy < 100:  # 25 => 2025 heuristic
                yy += 2000
            try:
                return datetime(yy, int(mm), int(dd), tzinfo=timezone.utc)
            except Exception:
                pass
    # 4) fallback: now
    return datetime.now(timezone.utc)

def looks_purdue(text):
    t = (text or "").lower()
    return any(k in t for k in (
        "purdue", "boilermaker", "matt painter", "mackey", "west lafayette",
        "boilermakers", "trey kaufman", "zach edey", "braden smith", "mason gillis"
    ))

def to_item(source, title, url, summary, dt):
    return {
        "id": sha(canonical_url(url) + title),
        "source": source,
        "title": decode(title)[:280],
        "url": url,
        "summary": decode(summary)[:400],
        "date": dt.astimezone(timezone.utc).isoformat(),
    }

# -------------------------
# News feeds
# -------------------------
FEEDS = [
    # Purdue official
    ("Purdue Athletics MBB", "https://purduesports.com/rss?path=mbball"),
    # Yahoo college basketball (broad; will be filtered)
    ("Yahoo Sports College Basketball", "https://www.yahoo.com/news/rss/college-basketball"),
    # ESPN Purdue team news
    ("ESPN Purdue MBB", "https://www.espn.com/college-basketball/team/_/id/2509/purdue-boilermakers"),
    # CBS college basketball (broad; filtered)
    ("CBS Sports College Basketball", "https://www.cbssports.com/rss/headlines/college-basketball/"),
    # SI Purdue (has Purdue tag page RSS)
    ("Sports Illustrated — Purdue", "https://www.si.com/college/purdue/.rss"),
    # The Field of 68 (broad articles; filtered)
    ("The Field of 68", "https://www.youtube.com/feeds/videos.xml?channel_id=UCtgu-ouR3de2Ww5QQB6W4_Q"),
]

def fetch_feed(name, url):
    items = []
    try:
        if url.endswith(".xml") or url.endswith(".rss") or "/rss" in url or "feeds" in url or "rss?" in url:
            d = feedparser.parse(url)
            for e in d.entries[:50]:
                link = e.get("link") or e.get("id") or ""
                title = e.get("title") or ""
                summary = e.get("summary") or e.get("description") or ""
                dt = parse_datetime_guess(e)
                items.append(to_item(name, title, link, summary, dt))
        else:
            # Basic HTML scrape for ESPN team page
            if "espn.com/college-basketball/team" in url:
                res = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
                res.raise_for_status()
                soup = BeautifulSoup(res.text, "html.parser")
                # grab headline cards that mention Purdue
                for a in soup.select("a[href]"):
                    href = a.get("href","")
                    text = (a.get_text(" ", strip=True) or "")
                    if not href or not text: 
                        continue
                    if not looks_purdue(text):
                        continue
                    if href.startswith("/"):
                        href = urljoin("https://www.espn.com", href)
                    dt = datetime.now(timezone.utc)
                    items.append(to_item("ESPN Purdue MBB", text, href, "", dt))
            else:
                # default try as feed
                d = feedparser.parse(url)
                for e in d.entries[:50]:
                    link = e.get("link") or e.get("id") or ""
                    title = e.get("title") or ""
                    summary = e.get("summary") or e.get("description") or ""
                    dt = parse_datetime_guess(e)
                    items.append(to_item(name, title, link, summary, dt))
    except Exception as ex:
        print(f"[feed-error] {name}: {ex}")
    return items

def collect_news():
    raw = []
    for name, url in FEEDS:
        raw.extend(fetch_feed(name, url))

    # Filter to Purdue MBB
    filtered = []
    for it in raw:
        text = f"{it['title']} {it['summary']}"
        if looks_purdue(text):
            filtered.append(it)

    # Deduplicate by canonical URL or title
    seen = set()
    dedup = []
    for it in filtered:
        key = (canonical_url(it["url"]) or "") + "||" + it["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(it)

    # Sort desc by date
    dedup.sort(key=lambda x: x["date"], reverse=True)
    return dedup[:20]

# -------------------------
# On3 board (Free Board – Purdue MBB)
# -------------------------
BOARD_URL = "https://www.on3.com/boards/forums/free-board-boilermaker-mens-basketball.160/"

def parse_relative_when(s: str) -> datetime:
    s = (s or "").strip().lower()
    # patterns like "9 hours ago", "10 minutes ago"
    m = re.search(r"(\d+)\s+(minute|hour|day|week)s?\s+ago", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        dt = datetime.now(timezone.utc)
        if unit.startswith("minute"):
            dt -= timedelta(minutes=n)
        elif unit.startswith("hour"):
            dt -= timedelta(hours=n)
        elif unit.startswith("day"):
            dt -= timedelta(days=n)
        elif unit.startswith("week"):
            dt -= timedelta(weeks=n)
        return dt
    # absolute like "Oct 29, 2025" or "10/27/25"
    for fmt in ("%b %d, %Y", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)

def collect_board():
    out = []
    try:
        res = requests.get(BOARD_URL, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # XenForo thread rows
        for row in soup.select("div.structItem--thread")[:30]:
            a = row.select_one("a.structItem-title")
            if not a:
                a = row.select_one("a.PreviewTooltip")
            if not a:
                continue
            title = decode(a.get_text(" ", strip=True))
            href = a.get("href", "")
            if href.startswith("/"):
                href = urljoin("https://www.on3.com", href)

            # forum name & timestamp
            forum = soup.select_one("h1.p-title-value")
            forum_name = forum.get_text(" ", strip=True) if forum else "On3 Free Board"

            ts = ""
            time_el = row.select_one("time")
            if time_el and time_el.get("datetime"):
                ts = time_el.get("datetime")
                dt = parse_datetime_guess({"published": ts})
            else:
                sub = row.select_one("div.structItem-minor")
                ts_text = sub.get_text(" ", strip=True) if sub else ""
                dt = parse_relative_when(ts_text)

            # author
            author_el = row.select_one("a.username")
            author = author_el.get_text(strip=True) if author_el else ""

            out.append({
                "id": sha(href + title),
                "forum": forum_name,
                "title": title,
                "url": href,
                "author": author,
                "date": dt.astimezone(timezone.utc).isoformat()
            })
    except Exception as ex:
        print(f"[board-error] {ex}")
    # Sort desc newest
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:20]

# -------------------------
# Main
# -------------------------
def main():
    news = collect_news()
    board = collect_board()

    # Write news
    items_path = os.path.join(OUT_DIR, "items.json")
    with open(items_path, "w", encoding="utf-8") as f:
        json.dump({
            "team": TEAM_SLUG,
            "updated": now_iso(),
            "count": len(news),
            "items": news
        }, f, ensure_ascii=False, indent=2)

    # Write board
    board_path = os.path.join(OUT_DIR, "board.json")
    with open(board_path, "w", encoding="utf-8") as f:
        json.dump({
            "team": TEAM_SLUG,
            "updated": now_iso(),
            "count": len(board),
            "threads": board
        }, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(news)} news items → {items_path}")
    print(f"Wrote {len(board)} board threads → {board_path}")

if __name__ == "__main__":
    main()