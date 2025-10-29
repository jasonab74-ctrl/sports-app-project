#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Purdue Men's Basketball Collector (News + RSS)
----------------------------------------------
Pulls basketball news from On3 and other sources.
"""

import os, json, re, time, html, hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_PATH = os.path.join(ROOT, "static", "teams", "purdue-mbb", "items.json")
SRC_PATH = os.path.join(ROOT, "static", "sources.json")

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def clean(text: str) -> str:
    if not text:
        return ""
    txt = html.unescape(text)
    txt = re.sub(r"\s+", " ", BeautifulSoup(txt, "html.parser").get_text()).strip()
    return txt

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat()

def parse_epoch(struct_time):
    try:
        return int(time.mktime(struct_time))
    except Exception:
        return 0

def hostname(url):
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""

def make_hash(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------

NEG = re.compile(r"\b(football|volleyball|wrestling|soccer|softball|baseball|track|tennis|golf|women'?s)\b", re.I)
POS = re.compile(r"\b(purdue|boilermakers?|painter|basketball|mbb|mackey)\b", re.I)

def likely_purdue_mbb(text: str) -> bool:
    t = text.lower()
    return bool(POS.search(t)) and not NEG.search(t)

# ---------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------

session = requests.Session()
session.headers.update({
    "User-Agent": "sports-app-project/1.0 (+https://github.com/jasonab74-ctrl)"
})

# ---------------------------------------------------------------------
# Source scrapers
# ---------------------------------------------------------------------

def scrape_on3_news(url: str):
    """Scrape the On3 Purdue Basketball News page."""
    out = []
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        cards = soup.select("article, div.card, a[data-vars-content-type='article']")
        for c in cards:
            a = c.find("a", href=True)
            if not a: continue
            title = clean(a.get_text())
            link = urljoin(url, a["href"])
            if not title or len(title) < 10: 
                continue
            if not likely_purdue_mbb(title):
                continue
            desc_el = c.find("p") or c.find("div", class_=re.compile("summary|dek"))
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
        print(f"[WARN] On3 scrape failed: {e}")
    return out

def scrape_generic_html(url: str, source_name: str):
    out = []
    try:
        r = session.get(url, timeout=15)
        if r.status_code >= 400:
            return out
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            title = clean(a.text)
            if len(title) < 15:
                continue
            link = urljoin(url, a["href"])
            if not likely_purdue_mbb(title):
                continue
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
        for e in feed.entries[:50]:
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

def main():
    with open(SRC_PATH, "r", encoding="utf-8") as f:
        srcs = json.load(f)["feeds"]

    all_items = []
    seen = set()

    for s in srcs:
        name = s.get("name", "Source")
        url = s.get("url", "")
        stype = s.get("type", "rss")

        items = []
        if "on3.com/teams/purdue-boilermakers/category/basketball/news" in url:
            items = scrape_on3_news(url)
        elif stype == "rss":
            items = parse_rss(url, name)
        else:
            items = scrape_generic_html(url, name)

        for it in items:
            key = make_hash(it["title"] + it["url"])
            if key in seen:
                continue
            seen.add(key)
            all_items.append(it)

    # Sort newest → oldest
    def sort_key(x):
        try:
            return datetime.fromisoformat(x["published"]).timestamp()
        except Exception:
            return 0

    all_items.sort(key=sort_key, reverse=True)
    final_items = all_items[:20]

    data = {
        "team": "purdue-mbb",
        "generated_at": now_iso(),
        "count": len(final_items),
        "items": final_items
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(final_items)} → {OUT_PATH}")

if __name__ == "__main__":
    main()