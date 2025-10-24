import os, json, yaml, feedparser, tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

# ---------- Tunables ----------
MAX_RESULTS = 20                   # only surface top 20
MAX_AGE_DAYS = 10                  # ignore anything older than ~10 days
DEDUP_TITLE_SIM_THRESHOLD = 85     # merge near-duplicate stories
RECENCY_HALFLIFE_HOURS = 18.0      # how fast "recency weight" decays
FEED_HEADERS = {"User-Agent": "Mozilla/5.0 PurdueMBBHub/1.0"}

# Trust weight: higher = more likely to float toward top
TRUST_WEIGHTS = {
    "official": 1.00,
    "insiders": 0.95,
    "beat":     0.90,
    "local":    0.80,
    "national": 0.75,
    "blog":     0.60,
    "fan_forum":0.50
}

# ---------- Helpers ----------
def _canonicalize_url(url):
    if not url: return ""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def _parse_date(entry):
    # try feed timestamps in priority order
    for key in ("published_parsed","updated_parsed","created_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except:
                pass
    # fallback: now (keeps it from being dropped completely)
    return datetime.now(timezone.utc)

def _normalize_item(source_name, trust_level, entry):
    link = entry.get("link") or ""
    title = (entry.get("title") or "").strip()
    summary = (entry.get("summary") or entry.get("description") or "").strip()

    # Some feeds provide media thumbnails in media_content/media_thumbnail
    thumb = None
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(media, list) and media:
        thumb = media[0].get("url")

    dt = _parse_date(entry)

    return {
        "source": source_name,
        "trust": trust_level,
        "title": title,
        "link": link,
        "date": dt.isoformat(),
        "summary": summary[:500],
        "image": thumb
    }

def _is_mbb_related(item):
    """
    Safety filter. We already query for Purdue men’s basketball but Google News
    can still sneak in junk (campus news, football).
    We'll keep if the title/summary includes some expected words.
    Tune this if it hides legit content.
    """
    text = f"{item.get('title','')} {item.get('summary','')}".lower()

    keep_terms = [
        "purdue", "boilermaker", "boilermakers", "painter", "matt painter",
        "big ten", "b1g", "guard", "forward", "center", "recruit", "commit",
        "ncaa tournament", "exhibition", "tipoff", "preseason",
        "men's basketball", "mens basketball", "basketball team"
    ]
    reject_terms = [
        "football", "quarterback", "qb", "touchdown", "nfl", "coach walters"
    ]

    if any(t in text for t in reject_terms):
        return False
    if any(t in text for t in keep_terms):
        return True
    # default is False (be strict so we don't bring in non-basketball Purdue)
    return False

def _dedup(items):
    """
    Merge near-duplicates based on URL and fuzzy title similarity.
    """
    out = []
    seen_urls = set()

    for it in items:
        url = _canonicalize_url(it.get("link"))
        title = (it.get("title") or "").strip().lower()

        # Same URL? skip
        if url and url in seen_urls:
            continue

        # Fuzzy title match against what's already kept
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

def _recency_weight(dt):
    """
    Newer = higher weight, decays ~exponentially with RECENCY_HALFLIFE_HOURS
    """
    now = datetime.now(timezone.utc)
    hours_old = max(0, (now - dt).total_seconds() / 3600.0)
    # half-life style decay
    return 0.5 ** (hours_old / RECENCY_HALFLIFE_HOURS)

def _score(item):
    trust_raw = (item.get("trust") or "").lower()
    trust_val = TRUST_WEIGHTS.get(trust_raw, 0.6)

    try:
        dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)

    rec_val = _recency_weight(dt)

    # Blend recency + source quality
    # recency dominates (70%), trust informs tie-break (30%)
    return (0.7 * rec_val) + (0.3 * trust_val)

def _atomic_write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=os.path.dirname(path), encoding="utf-8") as tmp:
        json.dump(obj, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

# ---------- main collection ----------

def collect_team(slug, feeds, out_path):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    raw_items = []

    # 1. pull from each feed
    for feed_conf in feeds:
        source_name = feed_conf.get("name","Source")
        trust_level = feed_conf.get("trust_level","national")
        url = feed_conf.get("url")
        if not url:
            continue

        parsed = feedparser.parse(url, request_headers=FEED_HEADERS)

        for entry in parsed.entries[:50]:
            it = _normalize_item(source_name, trust_level, entry)

            # discard old stuff
            try:
                dt = datetime.fromisoformat(it["date"].replace("Z","+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
            if dt < cutoff:
                continue

            # discard if not clearly Purdue MBB
            if not _is_mbb_related(it):
                continue

            raw_items.append(it)

    # 2. dedupe across all sources
    deduped = _dedup(raw_items)

    # 3. sort by score (recency + trust), take top 20
    deduped.sort(key=_score, reverse=True)
    top_items = deduped[:MAX_RESULTS]

    # 4. write to disk (only if at least 1 item)
    if not top_items:
        print(f"[{slug}] No qualifying Purdue MBB stories found. Keeping old file.")
        return

    _atomic_write(out_path, {"items": top_items})
    print(f"[{slug}] wrote {len(top_items)} items -> {out_path}")

def main():
    # read feeds.yaml
    conf = yaml.safe_load(open("src/feeds.yaml","r",encoding="utf-8"))

    teams_env = os.environ.get("TEAMS","").strip()
    teams = [t.strip() for t in teams_env.split(",") if t.strip()] if teams_env else list(conf.keys())
    if not teams:
        raise SystemExit("No teams configured.")

    for team in teams:
        if team not in conf:
            print(f"Team {team} not in feeds.yaml; skipping.")
            continue
        output_path = f"static/teams/{team}/items.json"
        collect_team(team, conf[team], output_path)

if __name__ == "__main__":
    main()