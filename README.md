# Sports App Project — Purdue MBB Hub

Mobile-first, GitHub Pages–hosted hub that **always loads instantly**:
- Renders **inline seed** headlines & videos immediately.
- **Upgrades** from `static/teams/purdue-mbb/items.json` when available.
- **Panels moved to JS** for stability: Rankings, Roster, Insiders are hydrated by `static/js/pro.js` with graceful fallbacks (empty UI is fine if JSON missing).

## Auto-update (GitHub Actions)
- `.github/workflows/collect.yml` runs every 30 minutes and on manual dispatch.
- Installs `feedparser`, `beautifulsoup4`, `pyyaml`, `rapidfuzz`.
- Executes `python src/collect.py`.
- Commits updates to `static/teams/purdue-mbb/items.json`.

## Data files
- `static/teams/purdue-mbb/items.json` — news+videos (auto).
- `static/widgets.json` — rankings: `{ ap_rank, kenpom_rank, ap_url, kenpom_url, updated_at }`.
- `static/insiders.json` — insider links: array of `{ name, url, latest_headline, latest_url, type, pay, updated_at }`.
- `static/teams/purdue-mbb/roster.json` — roster array with `{ num, name, pos, ht, wt, class, hometown }`.
- `static/schedule.json` — upcoming games (still hydrated inline for determinism).

## Notes
- Path base is `/sports-app-project/`. If you fork to another repo, update the base passed to `PRO.hydratePanels()` or keep the same path.
- `sw.js` remains a self-destruct worker to avoid cache issues.
- `tools/collect.py` is a shim delegating to `src/collect.py`.
