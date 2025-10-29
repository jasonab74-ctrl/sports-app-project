// CONFIG
const TEAM_SLUG = "purdue-mbb";
const ITEMS_URL = `./static/teams/${TEAM_SLUG}/items.json`; // <-- relative so it works on GitHub Pages

const MAX_ARTICLES = 20;

// DOM refs
const headlineListEl = document.getElementById("headline-list");
const emptyStateEl   = document.getElementById("empty-state");
const updatedRowEl   = document.getElementById("updated-row");
const updatedAtEl    = document.getElementById("updated-at");
const sourceListEl   = document.getElementById("source-list");

// Render one card
function renderCard(item) {
  const card = document.createElement("article");
  card.className = "story-card";

  const src = document.createElement("div");
  src.className = "story-source";
  src.textContent = item.source || "Unknown";

  const link = document.createElement("a");
  link.className = "story-headline";
  link.href = item.link || "#";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = item.title || "(no title)";

  const dt = document.createElement("div");
  dt.className = "story-date";
  dt.textContent = formatDate(item.date);

  card.appendChild(src);
  card.appendChild(link);
  card.appendChild(dt);

  return card;
}

// Format ISO date -> "Oct 25"
function formatDate(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

// Updated timestamp "Last updated 6:14 PM"
function setUpdated(tsMillis) {
  if (!tsMillis) return;
  const d = new Date(tsMillis);
  const stamp = d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
  updatedAtEl.textContent = `Last updated ${stamp}`;
  updatedRowEl.hidden = false;
}

// Build sources list
function renderSources(uniqueSources) {
  // Wipe
  sourceListEl.innerHTML = "";

  // Turn simple array like:
  // ["Hammer & Rails","GoldandBlack","On3 Purdue", ...]
  // into rows with a short blurb. We can hardcode blurbs here.
  const blurbs = {
    "Hammer & Rails":
      "SB Nation Purdue coverage / longtime beat voices",
    "GoldandBlack":
      "Insider access, recruiting, practice notes",
    "On3 Purdue":
      "On3 recruiting & roster intel",
    "Journal & Courier":
      "Local Lafayette / West Lafayette reporting",
    "Yahoo Sports":
      "National college hoops context",
    "CBS Sports":
      "Big Ten / national analysis",
    "ESPN":
      "National NCAA hoops coverage",
    "PurdueSports":
      "Official Purdue athletics releases"
  };

  uniqueSources.forEach(srcName => {
    const row = document.createElement("li");
    row.className = "source-row";

    const bullet = document.createElement("div");
    bullet.className = "source-bullet";

    const body = document.createElement("div");
    body.className = "source-body";

    const nameEl = document.createElement("div");
    nameEl.className = "source-name";
    nameEl.textContent = srcName;

    const descEl = document.createElement("div");
    descEl.className = "source-desc";
    descEl.textContent = blurbs[srcName] || "";

    body.appendChild(nameEl);
    body.appendChild(descEl);

    row.appendChild(bullet);
    row.appendChild(body);

    sourceListEl.appendChild(row);
  });
}

// Main render
function renderAll(payload) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  const updated_ts = payload.updated_ts || Date.now();

  // sort newest -> oldest by .date desc
  items.sort((a, b) => {
    const ta = Date.parse(a.date || "") || 0;
    const tb = Date.parse(b.date || "") || 0;
    return tb - ta;
  });

  const clipped = items.slice(0, MAX_ARTICLES);

  if (clipped.length === 0) {
    // show empty state
    headlineListEl.innerHTML = "";
    emptyStateEl.hidden = false;
  } else {
    emptyStateEl.hidden = true;
    headlineListEl.innerHTML = "";
    clipped.forEach(item => {
      headlineListEl.appendChild(renderCard(item));
    });
  }

  // updated timestamp
  setUpdated(updated_ts);

  // sources
  const srcs = [...new Set(clipped.map(i => i.source || "Unknown"))];
  renderSources(srcs);
}

// Fetch and init
function init() {
  fetch(ITEMS_URL, { cache: "no-store" })
    .then(res => {
      if (!res.ok) throw new Error("Failed to load items.json");
      return res.json();
    })
    .then(data => {
      renderAll(data);
    })
    .catch(err => {
      console.error(err);
      // if we fail to load, show empty message
      emptyStateEl.hidden = false;
    });
}

init();