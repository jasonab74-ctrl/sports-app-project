  # Team Hub (Static, GitHub Pages Only)


A **zero-backend**, self-updating team news hub.  
GitHub Actions collects trusted sources and writes ranked, de-duplicated JSON to `/static/teams/<team>/items.json`.  
The frontend (this repo’s `index.html`) fetches that JSON and renders a clean **Daily Brief** + **Top Feed**.

- ✅ 100% GitHub (Pages + Actions)
- ✅ No servers, no databases
- ✅ Scales to many teams by editing one YAML file

---

## Quick Start

### 1) Create or use a repo named **`sports-app-project`**
Push these files to the root:

sports-app-project/
├── index.html
├── README.md
├── static/
│ ├── css/styles.css
│ ├── js/app.js
│ └── teams/
│ └── purdue-mbb/items.json # seed file (empty; Action will replace)
├── src/
│ ├── feeds.yaml
│ └── collect.py
└── .github/workflows/collect.yml

### 2) Enable GitHub Actions permissions
- Repo **Settings → Actions → General → Workflow permissions** → set to **Read and write permissions**.  
  This allows the workflow to commit `items.json` back to `main`.

### 3) Enable GitHub Pages
- **Settings → Pages** → under **Build and deployment**, choose **GitHub Actions** (recommended).

### 4) Commit to `main`
- The workflow runs **every 30 minutes** and on **manual dispatch**.
- First successful run will write `static/teams/purdue-mbb/items.json` with live stories.

Your site will be hosted at:

https://<your-username>.github.io/sports-app-project/

---

## How It Works

1. **Collector (`src/collect.py`)**  
   - Fetches multiple feeds per team (RSS/YouTube/Reddit).  
   - Scores items by **trust** and **recency** (exponential decay).  
   - De-duplicates by **canonical URL** and **fuzzy title match**.  
   - Writes the top items to `static/teams/<team>/items.json`.

2. **Workflow (`.github/workflows/collect.yml`)**  
   - Runs every 30 minutes and on demand.  
   - Installs Python deps and executes the collector.  
   - Commits JSON changes back to `main`.

3. **Frontend (`index.html` + `static/js/app.js`)**  
   - Loads `/static/teams/<team>/items.json`.  
   - Shows **Daily Brief** (top 8) and **Top Feed** (top 50).  
   - No backend calls — fully static.

---

## Configure Feeds (Add/Update Teams)

Edit **`src/feeds.yaml`** to set sources and trust levels:

```yaml
purdue-mbb:
  - name: Purdue Athletics (Official MBB)
    url: https://purduesports.com/rss.aspx?path=mbball
    type: rss
    trust_level: official

  - name: Journal & Courier Purdue
    url: https://rssfeeds.jconline.com/purdue/mbb
    type: rss
    trust_level: local

  - name: GoldandBlack.com (On3)
    url: https://www.on3.com/teams/purdue-boilermakers/feed/
    type: rss
    trust_level: beat

  - name: Hammer and Rails (SB Nation)
    url: https://www.hammerandrails.com/rss/current
    type: rss
    trust_level: blog

  - name: r/CollegeBasketball (search Purdue)
    url: https://www.reddit.com/r/CollegeBasketball/search.rss?q=Purdue&restrict_sr=on&sort=new&t=week
    type: rss
    trust_level: fan_forum

  - name: YouTube Highlights (query Purdue Basketball)
    url: https://www.youtube.com/feeds/videos.xml?search_query=Purdue+Basketball
    type: rss
    trust_level: national

  - name: CBS Sports Purdue
    url: https://www.cbssports.com/college-basketball/teams/PUR/purdue-boilermakers/rss/
    type: rss
    trust_level: national

EXAMPLE - 

philadelphia-eagles:
  - name: Official
    url: https://www.philadelphiaeagles.com/rss/rss.jsp?feed=news
    type: rss
    trust_level: official
  # add beat/national/local/blog/forum/YouTube sources here...
