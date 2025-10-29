# Purdue Men's Basketball News Feed

This repo serves one job: show the latest Purdue men's basketball stories in a clean, mobile-friendly grid.

## How it works
- `/index.html` is the page.
- `/static/css/pro.css` handles the Purdue black/gold theme.
- `/static/js/pro.js` loads JSON and draws the cards.
- `/static/teams/purdue-mbb/items.json` holds the stories (source, title, link, timestamp, snippet, image).

The page will render the first 20 items from `items.json`. Newest item should be first. `collected_at` is used to show "Updated HH:MM" in the header.

There are no other widgets. No roster, no schedule, no NIL, no bloat.