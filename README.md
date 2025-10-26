# Purdue MBB Hub

Auto-updating Purdue Men's Basketball headlines.

- Scrapes ~10 trusted Purdue MBB sources (see src/feeds.yaml)
- Keeps only the last 72 hours
- Dedupes + sorts newest first
- Publishes top 20 to static/teams/purdue-mbb/items.json
- Front end (index.html + pro.css + pro.js) renders that list

## How it runs
1. .github/workflows/collect.yml runs every 15 min
   - runs collect.py
   - writes static/teams/purdue-mbb/items.json
   - commits/pushes if changed
2. .github/workflows/deploy.yml runs on push to main
   - deploys site to GitHub Pages via Actions (Settings -> Pages -> Source: GitHub Actions)

## You visit:
https://<your-username>.github.io/sports-app-project/

You're done.
