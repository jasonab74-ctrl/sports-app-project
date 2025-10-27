#!/usr/bin/env python3
"""
tools/collect.py

Minimal Purdue MBB collector.

- Reads RSS feeds from static/sources.json
- Pulls stories
- Filters to Purdue men's basketball
- Writes top 20 to static/teams/purdue-mbb/items.json
- No external libs required beyond Python stdlib
"""

import json
import datetime
import email.utils
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "static" / "sources.json"
ITEMS_PATH = ROOT / "static" / "teams" / "purdue-mbb" / "items.json"

KEYWORDS_ANY = [
    "purdue",
    "boilermaker",
    "boilermakers",
    "painter",
    "mackey",
    "boilers"
    # intentionally basketball-y names/coach/etc.
]

def http_get(url, timeout=10):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (URLError, HTTPError) as e:
        print("fetch fail", url, e)
        return b""

def parse_rss(xml_bytes, source_name):
    """Return list[dict] of items with title,url,published,snippet"""
    out = []
    if not xml_bytes:
        return out
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out

    # RSS 2.0: <channel><item>...
    channel = root.find("channel")
    items = []
    if channel is not None:
        items = channel.findall("item")
    else:
        # Atom fallback: <entry>
        items = root.findall("{http://www.w3.org/2005/Atom}entry")

    for it in items:
        title = (
            (it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title") or "")
            .strip()
        )
        link = it.findtext("link") or ""
        if not link:
            # atom style: <link href="...">
            link_el = it.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.attrib.get("href", "").strip()
        desc = (
            (it.findtext("description") or it.findtext("{http://www.w3.org/2005/Atom}summary") or "")
            .strip()
        )

        pub_raw = (
            it.findtext("pubDate")
            or it.findtext("{http://www.w3.org/2005/Atom}updated")
            or it.findtext("{http://www.w3.org/2005/Atom}published")
            or ""
        ).strip()

        # convert pub_raw -> ISO
        published_iso = None
        if pub_raw:
            try:
                dt = email.utils.parsedate_to_datetime(pub_raw)
                published_iso = dt.isoformat(timespec="seconds") + "Z"
            except Exception:
                # last resort: now
                published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        else:
            published_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        out.append({
            "source": source_name,
            "title": title,
            "url": link,
            "published": published_iso,
            "snippet": desc[:240].replace("\n", " ").strip(),
            "image": "",
            "collected_at": ""  # we'll stamp later
        })
    return out

def keep_purdue_mbb(stories):
    filtered = []
    for s in stories:
        text_blob = f"{s.get('title','')} {s.get('snippet','')}".lower()
        if any(k in text_blob for k in KEYWORDS_ANY):
            # must mention basketball context OR come directly from Purdue Athletics feed name
            if "basketball" in text_blob or "men" in text_blob or "mbb" in text_blob or "purdue athletics" in s.get("source","").lower():
                filtered.append(s)
    return filtered

def load_sources():
    try:
        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("sources", [])
    except Exception as e:
        print("failed to read sources.json", e)
        return []

def collect_all():
    sources = load_sources()
    all_items = []

    for src in sources:
        if src.get("type") != "rss":
            continue
        url = src.get("url")
        if not url:
            continue
        raw = http_get(url)
        items = parse_rss(raw, src.get("name",""))
        all_items.extend(items)

    # filter to Purdue MBB-ish only
    filtered = keep_purdue_mbb(all_items)

    # sort newest first by published
    def sort_key(item):
        try:
            return item["published"]
        except KeyError:
            return ""
    filtered.sort(key=sort_key, reverse=True)

    # keep top 20
    filtered = filtered[:20]

    # stamp collected_at for UI "Updated" badge
    now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for it in filtered:
        it["collected_at"] = now_iso

    return filtered

def save_items(items):
    out = {"items": items}
    ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

def main():
    stories = collect_all()
    if not stories:
        # fallback: keep whatever's already in items.json so the site isn't blank
        try:
            current = json.loads(ITEMS_PATH.read_text("utf-8"))
            existing_items = current.get("items", [])
        except Exception:
            existing_items = []
        if existing_items:
            # just refresh collected_at
            now_iso = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            for it in existing_items:
                it["collected_at"] = now_iso
            save_items(existing_items)
            return

    save_items(stories)

if __name__ == "__main__":
    main()