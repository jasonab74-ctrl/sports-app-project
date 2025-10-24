import os
import re
import json
import yaml
import feedparser
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

# ----------------------------
# Tunables
# ----------------------------
MAX_RESULTS = 20          # we only surface the rolling top 20
MAX_AGE_DAYS = 14         # look back ~2 weeks
DEDUP_TITLE_SIM_THRESHOLD = 85  # fuzzy title dedupe
FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (PurdueMBBHub/1.0)"
}

# Canonical source names so UI doesn't show messy variations
SOURCE_CANON = {
    "hammer & rails": "Hammer & Rails",
    "hammerandrials": "Hammer & Rails",

    "journal & courier": "Journal & Courier",
    "journal and courier": "Journal & Courier",
    "jconline": "Journal & Courier",

    "goldandblack": "GoldandBlack (Rivals)",
    "gold and black": "GoldandBlack (Rivals)",
    "rivals": "GoldandBlack (Rivals)",
    "goldandblack.com": "GoldandBlack (Rivals)",

    "on3 purdue": "On3 Purdue",
    "on3.com": "On3 Purdue",

    "espn": "ESPN",
    "espn.com": "ESPN",

    "yahoo sports": "Yahoo Sports",
    "sports.yahoo.com": "Yahoo Sports",

    "cbs sports": "CBS Sports",
    "cbssports.com": "CBS Sports",

    "field of 68": "Field of 68",
    "the athletic": "The Athletic",
    "theathletic.com": "The Athletic",

    "stadium / jeff goodman": "Stadium / Jeff Goodman",
    "watchstadium.com": "Stadium / Jeff Goodman",

    "associated press (ap)": "Associated Press (AP)",
    "associated press (cbb)": "Associated Press (AP)",
    "ap news": "Associated Press (AP)",
    "apnews.com": "Associated Press (AP)",

    "big ten network": "Big Ten Network",
    "btn.com": "Big Ten Network",
}

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

def canon_source(raw):
    if not raw:
        return "Unknown"
    key = raw.strip().lower()
    return SOURCE_CANON.get(key, raw.strip())

def _canonicalize_url(url):
    if not url:
        return ""
    p = urlparse(url)
    # strip query/fragment for dedup
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def _parse_date(entry):
    """
    Try published_parsed, updated_parsed, created_parsed.
    Fall back to now (UTC).
    """
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def _extract_best_image(entry, summary_html):
    """
    Thumbnail strategy:
    1. RSS media_content/media_thumbnail
    2. First <img src="..."> in summary HTML
    """
    media_blocks = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media_blocks, list) and media_blocks:
        candidate = media_blocks[0].get("url")
        if candidate:
            return candidate

    if summary_html:
        m = IMG_TAG_RE.search(summary_html)
        if m:
            return m.group(1)

    return None

def _normalize_item(source_name, trust_level, entry):
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary_html = (entry.get("summary") or entry.get("description") or "").strip()

    pub_dt = _parse_date(entry)
    thumb = _extract_best_image(entry, summary_html)

    return {
        "source": canon_source(source_name),
        # we still record trust_level but we don't use it for ordering anymore
        "trust": trust_level,
        "title": title,
        "link": link,
        "date": pub_dt.isoformat(),   # ISO 8601 UTC
        "summary": summary_html[:500],
        "image": thumb
    }

def _is_mbb_related(item):
    """
    Purdue Men's Basketball relevance test (relaxed):
    - Must mention Purdue somehow
    - Reject obvious "football only"
    - Allow roster / camp / outlook / Painter / preseason even if 'basketball'
      isn't literally in the headline
    """
    text = f"{item.get('title','')} {item.get('summary','')}".lower()

    # must reference Purdue in some way
    if not any(w in text for w in ["purdue", "boilermaker", "boilermakers"]):
        return False

    # reject obvious football content so football updates don't drown us
    reject_terms = [
        "football", "qb", "quarterback", "touchdown",
        "wide receiver", "linebacker", "defensive coordinator",
        "ryan walters", "coach walters", "walters' defense"
    ]
    if any(r in text for r in reject_terms):
        return False

    # If it smells like hoops / roster / Painter / preseason, it's in
    hoops_terms = [
        "basketball", "guard", "forward", "center",
        "roster", "rotation", "backcourt", "frontcourt",
        "recruit", "recruiting", "commit", "commitment",
        "ncaa tournament", "camp standouts", "practice",
        "offseason check-in", "chemistry", "painter", "matt painter"
    ]
    if any(k in text for k in hoops_terms):
        return True

    # fallback: if it's Purdue and not obviously football, keep it.
    # This lets "Purdue outlook / ceiling / preseason expectations" through.
    return True

def _dedup(items):
    """
    Deduplicate by canonical URL OR fuzzy-similar title.
    """
    out = []
    seen_urls = set()

    for it in items:
        url = _canonicalize_url(it.get("link"))
        title = (it.get("title") or "").strip().lower()

        # exact same URL? skip
        if url and url in seen_urls:
            continue

        # fuzzy title check vs what we've already kept
        is_dup = False
        for oi in out:
            existing_title = (oi.get("title") or "").strip().lower()
            if fuzz.token_set_ratio(title, existing_title) >= DEDUP_TITLE_SIM_THRESHOLD:
                is_dup = True
                break

        if not is_dup:
            out.append(it)
            if url:
                seen_urls.add(url)

    return out

def _atomic_write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=os.path.dirname(path),
        encoding="utf-8"
    ) as tmp:
        json.dump(obj, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

def collect_team(team_slug, feeds, out_path):
    """
    Pull feeds for this team, filter to MBB-ish Purdue items,
    keep last ~14 days, dedupe, sort newest -> oldest,
    take top 20, write items.json.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    pulled_items = []

    for feed_conf in feeds:
        source_name = feed_conf.get("name", "Source")
        trust_level = feed_conf.get("trust_level", "national")
        url = feed_conf.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        for entry in parsed.entries[:50]:
            item = _normalize_item(source_name, trust_level, entry)

            # age gate
            try:
                dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)

            if dt < cutoff:
                continue

            # Purdue MBB-ish filter
            if not _is_mbb_related(item):
                continue

            pulled_items.append(item)

    # deduplicate similar stuff
    deduped = _dedup(pulled_items)

    # sort newest first by publish datetime
    def _dt(i):
        try:
            return datetime.fromisoformat(i["date"].replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
    deduped.sort(key=_dt, reverse=True)

    top_items = deduped[:MAX_RESULTS]

    if not top_items:
        print(f"[{team_slug}] No qualifying Purdue MBB stories. Keeping old file.")
        return

    _atomic_write(out_path, {"items": top_items})
    print(f"[{team_slug}] wrote {len(top_items)} items -> {out_path}")

def main():
    conf = yaml.safe_load(open("src/feeds.yaml", "r", encoding="utf-8"))

    teams_env = os.environ.get("TEAMS", "").strip()
    teams = [t.strip() for t in teams_env.split(",") if t.strip()] if teams_env else list(conf.keys())
    if not teams:
        raise SystemExit("No teams configured in feeds.yaml.")

    for team in teams:
        if team not in conf:
            print(f"Team {team} not found in feeds.yaml; skipping.")
            continue

        out_path = f"static/teams/{team}/items.json"
        collect_team(team, conf[team], out_path)

if __name__ == "__main__":
    main()