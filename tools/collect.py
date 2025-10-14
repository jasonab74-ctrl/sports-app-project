#!/usr/bin/env python3
# tools/collect.py
#
# Unified collector for Boilermakers Hub
# Builds normalized JSON for news, schedule, rankings
# Stdlib only — no third-party dependencies
# --------------------------------------------------

import os, re, json, time, html, sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "static", "data")
TEAM_KEY = "purdue-mbb"

UA = "Mozilla/5.0 (BoilermakersHub/1.0; +https://github.com/jasonab74-ctrl/sports-app-project)"
HEADERS = {"User-Agent": UA}

# ----------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------

def fetch(url, timeout=10):
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                print(f"[warn] {url} -> {r.status}")
                return None
            return r.read()
    except Exception as e:
        print(f"[warn] fetch {url}: {e}")
        return None


def iso(dt):
    if not dt:
        return None
    if isinstance(dt, (int, float)):
        d = datetime.fromtimestamp(dt, tz=timezone.utc)
    elif isinstance(dt, datetime):
        d = dt
    else:
        try:
            d = datetime.fromisoformat(str(dt).replace("Z", "+00:00"))
        except Exception:
            return None
    if not d.tzinfo:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def parse_date(text):
    if not text:
        return None
    s = str(text).strip()
    if s.endswith("ago"):
        return None
    # RFC or ISO
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            d = datetime.strptime(s, fmt)
            if not d.tzinfo:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).isoformat()
        except Exception:
            continue
    # epoch
    try:
        f = float(s)
        if f > 10_000_000_000:
            f /= 1000.0
        return iso(f)
    except Exception:
        return None


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def save_json(path, data):
    ensure_dir(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ----------------------------------------------------------------------
# Feeds
# ----------------------------------------------------------------------

FEEDS = {
    "official": [
        "https://purduesports.com/rss_feeds.aspx?path=mbball",
    ],
    "insiders": [
        "https://hammerandrails.com/rss",
        "https://247sports.com/college/purdue/rss/",
        "https://purdue.rivals.com/rss",
        "https://goldandblack.com/rss",
    ],
    "national": [
        "https://www.espn.com/espn/rss/ncb/news",
        "https://www.cbssports.com/partners/feeds/rss/nba/",
        "https://sports.yahoo.com/ncaab/rss/",
    ],
}

IMG_RE = re.compile(rb'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)
FOOTBALL = re.compile(r"\bfootball\b", re.I)
MBB_HINT = re.compile(r"\b(basketball|mbb|men['’]s)\b", re.I)
PURDUE = re.compile(r"\bpurdue|boilermaker|mackey|matt\s+painter\b", re.I)


def is_mbb(title, desc, src):
    blob = f"{title.lower()} {desc.lower()} {src.lower()}"
    if FOOTBALL.search(blob):
        return False
    return PURDUE.search(blob) and MBB_HINT.search(blob)


def parse_rss(xml_bytes, source_tag):
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        print(f"[warn] parse_rss: {e}")
        return []
    items = []
    for it in root.findall(".//item"):
        title = it.findtext("title") or ""
        link = it.findtext("link") or ""
        desc = html.unescape(it.findtext("description") or "")
        pub = parse_date(it.findtext("pubDate") or "")
        if not is_mbb(title, desc, source_tag):
            continue
        img = None
        enc = it.find("enclosure")
        if enc is not None:
            img = enc.attrib.get("url")
        items.append(
            {
                "title": title.strip(),
                "link": link.strip(),
                "source": source_tag,
                "tag": source_tag,
                "date": pub or iso(time.time()),
                "image": img,
            }
        )
    return items


def try_og_image(url):
    html_bytes = fetch(url, 6)
    if not html_bytes:
        return None
    m = IMG_RE.search(html_bytes)
    if m:
        try:
            val = m.group(1).decode("utf-8", "ignore").strip()
            if val.startswith(("http://", "https://")):
                return val
        except Exception:
            pass
    return None


def enrich_images(items):
    for x in items:
        if x.get("image"):
            continue
        if not x.get("link"):
            continue
        img = try_og_image(x["link"])
        if img:
            x["image"] = img
            time.sleep(0.2)  # gentle
    return items


# ----------------------------------------------------------------------
# Collectors
# ----------------------------------------------------------------------

def collect_news():
    all_items = []
    for tag, urls in FEEDS.items():
        subset = []
        for u in urls:
            xml = fetch(u)
            if not xml:
                continue
            parsed = parse_rss(xml, tag)
            subset.extend(parsed)
            time.sleep(0.5)
        if subset:
            subset = enrich_images(subset)
            path = os.path.join(DATA_DIR, f"news_{tag}.json")
            save_json(path, subset)
            all_items.extend(subset)
            print(f"[ok] {tag}: {len(subset)} items")
    # Merge
    seen = set()
    merged = []
    for it in sorted(all_items, key=lambda x: x.get("date", ""), reverse=True):
        link = it.get("link")
        if link in seen:
            continue
        seen.add(link)
        merged.append(it)
    save_json(os.path.join(DATA_DIR, "news_all.json"), merged)
    print(f"[ok] news_all.json {len(merged)} total")


def collect_rankings():
    # Example stub; your workflow may already pull this.
    ap = {"rank": 1, "source": "https://apnews.com/hub/ap-top-25-college-basketball-poll"}
    kenpom = {"rank": 2, "source": "https://kenpom.com/", "updated": iso(time.time())}
    data = {"ap": ap, "kenpom": kenpom}
    save_json(os.path.join(DATA_DIR, "rankings.json"), data)
    print("[ok] rankings.json")


def collect_schedule():
    # Fallback static; your existing job can overwrite this.
    sched = [
        {
            "name": "Kentucky (Exhibition)",
            "homeAway": "Away",
            "date": iso(datetime(2025, 10, 24, 15, 0, tzinfo=timezone.utc)),
            "where": "Rupp Arena — Lexington, KY",
            "link": "https://purduesports.com/sports/mens-basketball/schedule",
        }
    ]
    save_json(os.path.join("static", "teams", TEAM_KEY, "schedule.json"), sched)
    print("[ok] schedule.json")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    collect_news()
    collect_rankings()
    collect_schedule()
    print("[done] all collections complete")


if __name__ == "__main__":
    main()