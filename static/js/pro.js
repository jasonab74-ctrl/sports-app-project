// Fetch JSON helper
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

// Turn ISO timestamp into "2h ago", "3d ago", etc.
// Return "" if we can't parse it.
function timeAgo(iso) {
  if (!iso) return "";

  const thenMs = Date.parse(iso);
  if (isNaN(thenMs)) return "";

  const nowMs = Date.now();
  const diffMs = nowMs - thenMs;
  if (diffMs < 0) return "";

  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return diffMin + "m ago";

  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return diffHr + "h ago";

  const diffDay = Math.floor(diffHr / 24);
  return diffDay + "d ago";
}

// Build the feed into the DOM
function renderFeed(items) {
  const feedGrid = document.getElementById("feedGrid");
  feedGrid.innerHTML = "";

  // top 20 only
  const topItems = items.slice(0, 20);

  // header timestamp badge ("Updated 5:36 AM")
  const updatedEl = document.getElementById("lastUpdated");
  if (topItems.length && topItems[0].collected_at) {
    updatedEl.textContent = new Date(topItems[0].collected_at)
      .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } else {
    updatedEl.textContent = "recently";
  }

  topItems.forEach(article => {
    // Card root is still an <a> so the whole card is clickable
    const card = document.createElement("a");
    card.className = "feed-card";
    card.href = article.url || "#";
    card.target = "_blank";
    card.rel = "noopener noreferrer";

    // CARD BODY (no thumbnail anymore)
    const body = document.createElement("div");
    body.className = "feed-body feed-body-noimg";

    // metadata row: source + age
    const metaRow = document.createElement("div");
    metaRow.className = "feed-meta-row";

    const srcSpan = document.createElement("span");
    srcSpan.className = "feed-source";
    srcSpan.textContent = article.source || "Source";

    const ageSpan = document.createElement("span");
    ageSpan.className = "feed-age";
    const relAge = timeAgo(article.published);
    ageSpan.textContent = relAge;

    metaRow.appendChild(srcSpan);
    // Only append the "age" bit if it's not ""
    if (relAge !== "") {
      metaRow.appendChild(ageSpan);
    }

    // headline
    const headlineDiv = document.createElement("div");
    headlineDiv.className = "feed-headline";
    headlineDiv.textContent = article.title || "";

    // snippet
    const snippetDiv = document.createElement("div");
    snippetDiv.className = "feed-snippet";
    snippetDiv.textContent = article.snippet || "";

    // combine
    body.appendChild(metaRow);
    body.appendChild(headlineDiv);
    body.appendChild(snippetDiv);

    // assemble card
    card.appendChild(body);

    // add to page
    feedGrid.appendChild(card);
  });
}

// init on page load
(async function init(){
  const data = await getJSON(
    "static/teams/purdue-mbb/items.json",
    { "items": [] }
  );

  renderFeed(data.items || []);
})();