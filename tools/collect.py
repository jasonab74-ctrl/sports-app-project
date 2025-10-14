#!/usr/bin/env python3
import json, os, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_json(p: Path, default):
    try:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[collect] WARN could not read {p}: {e}", file=sys.stderr)
    return default

def dump_json(p: Path, obj):
    tmp = p.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

# ---------- Rankings passthrough (keeps your current builder) ----------
def ensure_rankings():
    src = ROOT / "static" / "data" / "rankings.json"
    # Nothing to do here; your existing job writes this.
    print(f"[collect] rankings passthrough: {src.exists()}")

# ---------- Beat links ----------
def ensure_beat_links():
    src = ROOT / "static" / "beat_links.json"
    out = DATA_DIR / "beat_links.json"
    items = load_json(src, {"links": []}).get("links", [])
    # Normalize
    cleaned = []
    for it in items:
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        if title and url:
            cleaned.append({"title": title, "url": url})
    dump_json(out, {"links": cleaned})
    print(f"[collect] wrote beat_links -> {out} ({len(cleaned)} items)")

# ---------- Schedule from overrides (safe + always available) ----------
def as_iso(date_str, time_str, tz):
    """Return ISO-8601 string with TZ in a safe, UI-friendly format.

    Input:
      date_str: 'YYYY-MM-DD'
      time_str: 'HH:MM' or None for TBD
      tz: IANA tz name or None
    """
    if not date_str:
        return None
    if not time_str:
        # date only
        return f"{date_str}T00:00:00{''}"
    # Keep as naive local wall-clock; UI formats with tz key we also emit.
    return f"{date_str}T{time_str}:00"

def ensure_schedule():
    overrides = ROOT / "static" / "schedule_overrides.json"
    out = DATA_DIR / "schedule.json"
    src = load_json(overrides, {"games": []}).get("games", [])
    cleaned = []
    for g in src:
        item = {
            "opponent": g.get("opponent"),
            "site": g.get("site"),  # Home/Away/Neutral
            "event": g.get("event"),  # Exhibition, Regular Season, etc (optional)
            "venue": g.get("venue"),
            "city": g.get("city"),
            "tz": g.get("tz") or "America/Indiana/Indianapolis",  # venue tz default
            "iso_local": as_iso(g.get("date"), g.get("time"), g.get("tz")),
            "link": g.get("link"),
        }
        # quick validity check
        if item["opponent"] and item["site"]:
            cleaned.append(item)

    # Sort by date/time if present
    def keyer(x):
        k = x.get("iso_local") or ""
        return k
    cleaned.sort(key=keyer)

    dump_json(out, {"games": cleaned, "generated_at": datetime.utcnow().isoformat() + "Z"})
    print(f"[collect] wrote schedule -> {out} ({len(cleaned)} games)")

def main():
    ensure_rankings()
    ensure_schedule()
    ensure_beat_links()

if __name__ == "__main__":
    main()
