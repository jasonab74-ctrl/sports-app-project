# Purdue MBB Hub (Modern — Dark Gray / Gold)

Mobile-first, auto-updating hub for Purdue Men’s Basketball.  
Built for GitHub Pages + GitHub Actions. Safe fallbacks ensure the site never renders blank.

## What's inside
- `index.html` — Single-page app
- `static/css/pro.css` — Modern dark-gray/gold theme
- `static/js/pro.js` — Fetches JSON and renders sections
- `static/widgets.json` — AP, KenPom, NIL (auto-upgrade later)
- `static/schedule.json` — Seed schedule
- `static/sources.json` — Quick links to trusted sources
- `static/teams/purdue-mbb/items.json` — Headlines (seed + auto-updated)
- `src/feeds.yaml` — Feeds to collect from
- `tools/collect.py` — Collector (uses `feeds.yaml`)
- `.github/workflows/collect.yml` — Runs every 30m (or manually)

## Deploy
1. Upload all files to your repo (default branch).
2. Ensure GitHub Pages is enabled for the repo (Settings ➜ Pages ➜ Source: `main` root).
3. Go to _Actions ➜ Collect Feeds ➜ Run workflow_ to update immediately.

## Customize for another team
- Duplicate `static/teams/purdue-mbb/` to new slug (e.g., `arizona-mbb`).
- Add feeds under that slug in `src/feeds.yaml`.
- Set `TEAMS` env in the workflow (comma-separated for multi-team).
