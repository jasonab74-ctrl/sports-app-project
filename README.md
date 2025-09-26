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

