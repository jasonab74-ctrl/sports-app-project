import os
import json
import yaml
import feedparser
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from rapidfuzz import fuzz

# -------------------------------
# Configuration
# -------------------------------
TRUST_WEIGHTS = {
    "official": 1.0,
    "beat": 0.9,
    "national": 0.8,
    "local": 0.75,
    "blog": 0.6,
    "fan_forum": 0.5
}

RECENCY_HALFLIFE_HOURS = 18.0   # how fast old stories lose weight
DEDUP_TITLE_SIM_THRESHOLD = 85  # fuzzy match threshold for title deduplication
DEFAULT_LIMIT = 200             # max items per team JSON file

# -------------------------------
# Utility Functions
# -------------------------------

def recency_weight(published_at: datetime) -> float:
    """Return a weight 0..1 based on how recent the item is."""
    if not published_at:
        return 0.5
    now = datetime.now(timezone.utc)
    hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    # exponential decay: halves every 18 hours (by default)
    return 0.5 ** (hours / RECENCY_HALFLIFE_HOURS)


def canonicalize_url(url: str) -> str:
    """Strip tracking params and standardize URL for deduplication."""
    if not url:
        return ""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def parse_dt(entry) -> datetime:
    """Parse datetime from a feed entry."""
    for key in ("published", "updated", "created"):
        if entry.get(key + "_parsed"):
            try:
                return datetime(*entry.get(key + "_parsed")[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def score_item(item: dict) -> float:
    """Compute a score based on trust level and recency."""
    trust = TRUST_WEIGHTS.get(item.get("trust_level"), 0.6)
    recency = item.get("recency", 0.5)
    return 0.55 * trust + 0.35 * recency + 0.10 * 0.0  # engagement placeholder


def dedupe(items: list) -> list:
    """Remove near-duplicate articles by URL or title similarity."""
    seen_urls = set()
    result = []
    for it in items:
        url = canonicalize_url(it["url"])
        if url in seen_urls:
            continue
        dup = False
        for kept in result:
            if fuzz.token_set_ratio(it["title"], kept["title"]) >= DEDUP_TITLE_SIM_THRESHOLD:
                dup = True
                break
        if not dup:
            result.append(it)
            seen_urls.add(url)
    return result

# -------------------------------
# Core Collector Logic
# -------------------------------

def collect_team(team: str, feeds: list, out_file: str):
    """Fetch all feeds for a team, rank, dedupe, and write JSON."""
    all_items = []

    for feed in feeds:
        print(f"Fetching {feed['name']} ({feed['url']})...")
        d = feedparser.parse(feed["url"])

        for e in d.entries[:50]:
            title = e.get("title") or "(no title)"
            url = canonicalize_url(e.get("link") or e.get("id") or "")
            if not url:
                continue
            published_at = parse_dt(e)
            item = {
                "team": team,
                "source": feed["name"],
                "source_type": feed.get("type", "rss"),
                "trust_level": feed.get("trust_level", "blog"),
                "title": title.strip(),
                "url": url,
                "guid": e.get("id") or e.get("guid") or url,
                "published_at": published_at.isoformat(),
                "recency": recency_weight(published_at),
                "image_url": extract_image(e),
                "author": e.get("author")
            }
            all_items.append(item)

    # Score, dedupe, and trim
    all_items.sort(key=score_item, reverse=True)
    all_items = dedupe(all_items)[:DEFAULT_LIMIT]

    # Save JSON output
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    payload = {
        "team": team,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"✅ Wrote {len(all_items)} items → {out_file}")


def extract_image(entry):
    """Try to pull an image URL if the feed includes one."""
    for key in ("media_thumbnail", "media_content", "links"):
        val = entry.get(key)
        if isinstance(val, list):
            for v in val:
                href = v.get("url") or v.get("href")
                if href and href.startswith("http"):
                    return href
    return None

# -------------------------------
# Entrypoint
# -------------------------------

def main():
    feeds_file = os.environ.get("FEEDS_FILE", "src/feeds.yaml")
    with open(feeds_file, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)

    teams = os.environ.get("TEAMS", "").strip()
    team_list = [t.strip() for t in teams.split(",") if t.strip()] if teams else list(conf.keys())

    for team in team_list:
        feeds = conf.get(team)
        if not feeds:
            print(f"⚠️ No feeds found for team: {team}")
            continue
        out_path = f"static/teams/{team}/items.json"
        collect_team(team, feeds, out_path)


if __name__ == "__main__":
    main()
