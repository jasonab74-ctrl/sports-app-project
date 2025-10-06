# Sports App Project — Purdue MBB Hub

Mobile-first, GitHub Pages–hosted hub that **always loads instantly**:
- Renders **inline seed** headlines & videos immediately.
- **Upgrades** from `static/teams/purdue-mbb/items.json` when available.
- **Panels in JS (`static/js/pro.js`)** with graceful fallbacks:
  - Rankings → `static/widgets.json`
  - Insiders → `static/insiders.json`
  - Roster → `static/teams/purdue-mbb/roster.json`
  - Schedule → `static/schedule.json`

## Auto-update (GitHub Actions)
- `.github/workflows/collect.yml` runs every 30 minutes and on manual dispatch.
- Installs `feedparser`, `beautifulsoup4`, `pyyaml`, `rapidfuzz`.
- Executes `python src/collect.py`.
- Commits updates to `static/teams/purdue-mbb/items.json`.

## Notes
- Path base is `/sports-app-project/`. If you fork to another repo, update the base you pass to `PRO.hydratePanels()` or keep the same path.
- `sw.js` remains a self-destruct worker to avoid cache issues.
- `tools/collect.py` is a shim delegating to `src/collect.py`.
