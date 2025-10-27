// static/js/pro.js
// Renders Purdue MBB feed onto the page.

// small fetch helper (with fallback if fetch fails)
async function getJSON(path, fallback) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error("status " + res.status);
    return await res.json();
  } catch (err) {
    console.warn("Could not load", path, err);
    return fallback;
  }
}

// "2h ago", "Oct 27, 2:15 PM"
function timeAgoOrStamp(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  const now = new Date();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);

  // if it's under 1 min
  if (diffMin < 1) return "just now";
  // under 60 min
  if (diffMin < 60) return diffMin + "m ago";

  const diffHr = Math.floor(diffMin / 60);
  // under 24h
  if (diffHr < 24) return diffHr + "h ago";

  // else show a timestamp like "Oct 27, 2:15 PM"
  // We'll include month short name + day + time
  const opts = {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  };
  return then.toLocaleString("en-US", opts);
}

// render list of feed stories to the grid
function renderFeed(items) {
  const feedGrid = document.getElementById("feedGrid");
  feedGrid.innerHTML = "";

  // limit top 20
  const topItems = items.slice(0, 20);

  // header "Updated <time>"
  const updatedEl = document.getElementById("lastUpdated");
  if (topItems.length && topItems[0].collected_at) {
    updatedEl.textContent =
      "Updated " +
      new Date(topItems[0].collected_at).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit"
      });
  } else {
    updatedEl.textContent = "Updated recently";
  }

  topItems.forEach(article => {
    // outer <a> so the whole card is tappable
    const card = document.createElement("a");
    card.className = "feed-card";
    card.href = article.url || "#";
    card.target = "_blank";
    card.rel = "noopener noreferrer";

    // card body wrapper
    const body = document.createElement("div");
    body.className = "feed-body";

    // meta row across top (source left, age right)
    const metaRow = document.createElement("div");
    metaRow.className = "feed-meta-row";

    const srcSpan = document.createElement("span");
    srcSpan.className = "feed-source";
    srcSpan.textContent = article.source || "Source";

    const ageSpan = document.createElement("span");
    ageSpan.className = "feed-age";
    ageSpan.textContent = timeAgoOrStamp(article.published || "");

    metaRow.appendChild(srcSpan);
    metaRow.appendChild(ageSpan);

    // headline
    const headlineDiv = document.createElement("div");
    headlineDiv.className = "feed-headline";
    headlineDiv.textContent = article.title || "";

    // snippet
    const snippetDiv = document.createElement("div");
    snippetDiv.className = "feed-snippet";
    snippetDiv.textContent = article.snippet || "";

    // assemble
    body.appendChild(metaRow);
    body.appendChild(headlineDiv);
    body.appendChild(snippetDiv);

    card.appendChild(body);
    feedGrid.appendChild(card);
  });
}

// render footer list of sources ("Sources we monitor:")
function renderSourcesFooter(items) {
  // gather unique non-empty sources, keep stable-ish order of appearance
  const seen = new Set();
  const orderedSources = [];
  items.forEach(it => {
    const s = (it.source || "").trim();
    if (s && !seen.has(s.toLowerCase())) {
      seen.add(s.toLowerCase());
      orderedSources.push(s);
    }
  });

  const sourceListEl = document.getElementById("sourceList");
  if (!sourceListEl) return;

  if (!orderedSources.length) {
    sourceListEl.textContent = "—";
    return;
  }

  // join with " · "
  sourceListEl.textContent = orderedSources.join(" · ");
}

// init
(async function init() {
  // load items.json
  const data = await getJSON(
    "static/teams/purdue-mbb/items.json",
    { items: [] }
  );

  const stories = data.items || [];

  renderFeed(stories);
  renderSourcesFooter(stories);
})();