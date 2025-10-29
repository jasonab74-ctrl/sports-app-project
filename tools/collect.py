import json, re, time, datetime
import feedparser
import requests
from bs4 import BeautifulSoup

# ----------------------------
# CONFIG: sources to crawl
# ----------------------------
SOURCES = [
    {
        "name": "Purdue Athletics MBB",
        "url": "https://purduesports.com/rss?path=mbball",
        "hard_purdue": True
    },
    {
        "name": "Yahoo Sports College Basketball",
        "url": "https://sports.yahoo.com/college-basketball/rss/",
        "hard_purdue": False
    },
    {
        "name": "ESPN Purdue MBB",
        "url": "https://www.espn.com/espn/rss/ncb/news",
        "hard_purdue": False
    },
    {
        "name": "CBS Sports College Basketball",
        "url": "https://www.cbssports.com/college-basketball/rss/all/",
        "hard_purdue": False
    },
    {
        "name": "SI Purdue Basketball",
        "url": "https://www.si.com/college/purdue/basketball/rss",
        "hard_purdue": True
    },
    {
        "name": "USA Today Purdue Boilermakers",
        "url": "https://feeds.feedblitz.com/purdue-boilermakers&x=1",
        "hard_purdue": True
    },
    {
        "name": "On3 Purdue Basketball",
        "url": "https://www.on3.com/college/purdue-boilermakers/feed/",  # often HTML, we'll try
        "hard_purdue": True,
        "is_html": True
    },
    {
        "name": "247Sports Purdue Basketball",
        "url": "https://247sports.com/college/purdue/Feed.rss",
        "hard_purdue": True
    },
    {
        "name": "The Field of 68",
        "url": "https://thefieldof68.com/feed/",
        "hard_purdue": False
    },
    {
        "name": "GoldandBlack.com",
        "url": "https://purdue.rivals.com/rss",  # many sites expose RSS; if this 404s, we just skip
        "hard_purdue": True
    },
]

# ----------------------------
# HELPERS
# ----------------------------

PURDUE_PATTERNS = [
    r"\bpurdue\b",
    r"\bboilermaker(s)?\b",
    r"\bmatt\s+painter\b",
    r"\bbraden\s+smith\b",
    r"\bboilermakers\b",
]

MBB_PATTERNS = [
    r"\bbasketball\b",
    r"\bmbb\b",
    r"\bmen'?s?\s+basketball\b",
]

def text_score(txt: str, hard_source: bool) -> int:
    """Score relevance of a story to Purdue men's basketball.
    Higher = more relevant.
    We're purposely generous so we don't filter out legit Purdue hoops.
    """
    if not txt:
        txt = ""
    t = txt.lower()

    score = 0

    # Purdue mentions
    for pat in PURDUE_PATTERNS:
        if re.search(pat, t):
            score += 2

    # Men's basketball mentions
    for pat in MBB_PATTERNS:
        if re.search(pat, t):
            score += 2

    # Explicit Purdue + basketball synergy bonus
    if re.search(r"\bpurdue\b", t) and re.search(r"basketball", t):
        score += 4

    # "Boilermakers" with basketball context etc
    if "boilermaker" in t and ("basketball" in t or "mbb" in t):
        score += 3

    # trusted Purdue-specific sites get a baseline boost
    if hard_source:
        score += 3

    return score


def clean_html_summary(s: str) -> str:
    if not s:
        return ""
    soup = BeautifulSoup(s, "html.parser")
    txt = soup.get_text(" ", strip=True)
    # collapse weird whitespace
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def fmt_date_short(epoch):
    """Return 'Oct 27' or 'Oct 27, 2025' if year != current."""
    if epoch is None:
        return ""
    dt = datetime.datetime.fromtimestamp(epoch)
    now = datetime.datetime.now()
    if dt.year == now.year:
        return dt.strftime("%b %d")
    else:
        return dt.strftime("%b %d, %Y")


def iso_timestamp(epoch):
    if epoch is None:
        return ""
    dt = datetime.datetime.fromtimestamp(epoch)
    return dt.isoformat()


def parse_entry(source_name, hard_src, entry):
    """Normalize one RSS/Atom entry to our internal shape."""
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()

    # summary / description
    summary = entry.get("summary") or entry.get("description") or ""
    summary = clean_html_summary(summary)

    # choose a published date
    published_epoch = None
    if "published_parsed" in entry and entry["published_parsed"]:
        published_epoch = time.mktime(entry["published_parsed"])
    elif "updated_parsed" in entry and entry["updated_parsed"]:
        published_epoch = time.mktime(entry["updated_parsed"])

    score_input_txt = " ".join([
        title,
        summary,
        source_name
    ])

    score_val = text_score(score_input_txt, hard_src)

    return {
        "title": title,
        "link": link,
        "summary": summary,
        "source": source_name,
        "published_epoch": published_epoch,
        "published_display": fmt_date_short(published_epoch),
        "published_iso": iso_timestamp(published_epoch),
        "score": score_val,
    }


def fetch_rss(url):
    """Return entries[] from an RSS/Atom URL using feedparser."""
    parsed = feedparser.parse(url)
    return parsed.entries or []


def fetch_html_cards(url, source_name, hard_src):
    """Some sites don't give clean RSS (like On3). We'll try basic scrape.
    We'll treat top div/article blocks as 'entries'.
    Super basic fallback.
    """
    out = []
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return out
        soup = BeautifulSoup(r.text, "html.parser")

        # grab headline blocks (very naive selectors)
        # On3 style often has <a data-testid="headline-link"> etc.
        article_links = soup.find_all("a")
        seen = set()
        now_epoch = time.time()

        for a in article_links:
            headline = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            if not headline or not href:
                continue
            # avoid dup
            key = (headline, href)
            if key in seen:
                continue
            seen.add(key)

            # build faux entry
            fake_entry = {
                "title": headline,
                "link": href if href.startswith("http") else href,
                "summary": "",
                "published_parsed": time.localtime(now_epoch),
            }
            out.append(parse_entry(source_name, hard_src, fake_entry))
    except Exception:
        pass
    return out


def collect_all():
    collected = []

    for src in SOURCES:
        name = src["name"]
        url = src["url"]
        hard_src = src.get("hard_purdue", False)
        is_html = src.get("is_html", False)

        try:
            if is_html:
                entries = fetch_html_cards(url, name, hard_src)
            else:
                raw_entries = fetch_rss(url)
                entries = [parse_entry(name, hard_src, e) for e in raw_entries]
        except Exception:
            entries = []

        collected.extend(entries)

    return collected


def pick_top_purdue(entries, limit=20):
    """Filter to Purdue men's basketball-ish, but DO NOT go empty.
    Strategy:
      1. Score every story.
      2. Take anything with score >= 5 (pretty Purdue MBB flavored).
      3. If that ends up empty, fall back to best-scoring Purdue Athletics MBB stories
         so we at least show something.
    Then sort newest -> oldest by published_epoch.
    """

    # first pass: high score
    primary = [e for e in entries if e["score"] >= 5]

    # fallback if empty
    if not primary:
        primary = [
            e for e in entries
            if "purdue" in e["source"].lower()
        ]

    # sort newest first using published_epoch
    def sort_key(e):
        # newer first means sort by (-epoch, -score as tiebreak)
        epoch = e["published_epoch"] if e["published_epoch"] else 0
        return (epoch, e["score"])

    primary.sort(key=sort_key, reverse=True)

    # chop to limit
    return primary[:limit]


def write_feed(items, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)


def main():
    raw = collect_all()
    top_items = pick_top_purdue(raw, limit=20)

    # final shape we actually write to disk that index.html expects
    final = []
    for e in top_items:
        final.append({
            "title": e["title"],
            "link": e["link"],
            "summary": e["summary"],
            "source": e["source"],
            "published": e["published_display"],   # "Oct 27"
            "published_iso": e["published_iso"],   # "2025-10-27T13:45:00"
        })

    # IMPORTANT: this path must exist in repo
    output_path = "static/teams/purdue-mbb/items.json"
    write_feed(final, output_path)

if __name__ == "__main__":
    main()