# Sports App Project — Purdue MBB Hub

Mobile-first, GitHub Pages–hosted hub that **always loads instantly**:
- Renders **inline seed** headlines & videos immediately.
- Then **optionally upgrades** from `static/teams/purdue-mbb/items.json`.
- Panels hydrate from JSON (`static/widgets.json`, `static/schedule.json`, `static/insiders.json`, `static/teams/purdue-mbb/roster.json`) with graceful fallbacks.

## Auto-update (GitHub Actions)
- Workflow: `.github/workflows/collect.yml`
- Runs every 30 min (and on manual dispatch).
- Installs `feedparser`, `beautifulsoup4`, `pyyaml`, `rapidfuzz`.
- Executes `python src/collect.py`
- Commits changes to `static/teams/purdue-mbb/items.json`.

## Collector
- Real collector: `src/collect.py` (uses `src/feeds.yaml`).
- Legacy path `tools/collect.py` is a **shim** that calls `src/collect.py` for compatibility.

## Data files
- `static/teams/purdue-mbb/items.json` — news+videos (auto).
- `static/widgets.json` — rankings with optional URLs.
- `static/schedule.json` — upcoming games.
- `static/insiders.json` — insider links.
- `static/teams/purdue-mbb/roster.json` — roster cards.

## Dev notes
- No persistent caching: `sw.js` is a self-destruct worker to avoid stale assets.
- Path base is `/sports-app-project/` for GitHub Pages.
- If you fork for another team, copy the `purdue-mbb` folder and adjust `feeds.yaml`.
