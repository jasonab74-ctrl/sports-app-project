# ⚙️ Sports App Project — Automation Workflows

This repository automatically updates and maintains itself using **GitHub Actions**.

---

## 🕒 1. Auto-Update Feeds (`.github/workflows/collect.yml`)

### 🔧 Purpose
Refreshes all team data (news, videos, schedule, rankings, insiders) on a schedule and cache-busts static assets so browsers always pull the latest version.

### 🧩 How It Works
1. Runs `tools/collect.py` to rebuild feed data.
2. Updates the version tags (`?v=YYYY-MM-DDTHH:MM:SSZ`) on:
   - `static/css/app.css`
   - `static/js/app.js`
   - `static/js/pro.js`
3. Commits and pushes changes to the `main` branch.

### 🗓️ Schedule
- **Default:** every 3 hours (`cron: "0 */3 * * *"`)
- **Alternative:** once daily at 6 AM Phoenix time
  ```yaml
  schedule:
    - cron: "0 13 * * *"   # 13:00 UTC == 06:00 Phoenix (no DST)
