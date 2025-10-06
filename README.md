⚙️ Automation & Maintenance
🕒 1. Auto-Update Feeds (.github/workflows/collect.yml)

This workflow automatically updates all live data and cache-busts your static assets.

What it does

Runs tools/collect.py every 3 hours to refresh all JSON feeds (news, videos, schedule, etc.).

Automatically bumps the version tags on:

static/css/app.css
static/js/app.js
static/js/pro.js


so browsers always fetch fresh content.

Commits and pushes updates directly to the main branch.

Manual triggers

You can also run it anytime from the Actions → Auto-update feeds → “Run workflow” button.

Changing frequency

Currently: every 3 hours.

To switch to a single daily update (6 AM Phoenix time), edit:

schedule:
  - cron: "0 13 * * *"


in collect.yml.

🧹 2. Weekly Repo Cleanup (.github/workflows/squash-auto-updates.yml)

This optional workflow keeps your commit history clean and fast.

What it does

Runs every Sunday at 5 AM Phoenix (12 UTC).

Keeps the most recent 20 commits (roughly 2–3 days at 3-hour intervals).

Squashes all older “Auto-update” commits into a single summary commit (Repo cleanup: preserve latest 20 commits).

Benefits

Reduces repo size and cluttered commit logs.

Keeps the main branch easy to review and fork.

Manual trigger

You can also run it on demand under Actions → Weekly Repo Cleanup → “Run workflow.”

🧭 Maintenance Notes

Both workflows are fully autonomous and require no tokens beyond the default GITHUB_TOKEN.

You can safely pause automation anytime by disabling workflows in the Actions tab.

For offseason periods, switch collect.yml to daily and disable the squash job if you prefer full commit history.

✅ Result:
Your GitHub Pages site (https://jasonab74-ctrl.github.io/sports-app-project/) now stays:

Self-updating every few hours

Cache-busted automatically

Clean and lightweight weekly
