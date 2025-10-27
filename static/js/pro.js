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

// "2h ago", "Oct 27", etc. If we can't parse, return "".
function timeAgoOrDate(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  if (isNaN(then.getTime())) return "";

  const now = new Date();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return diffMin + "m ago";

  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return diffHr + "h ago";

  const opts = { month: "short", day: "numeric" };
  return then.toLocaleDateString(undefined, opts);
}

// Put the pretty "Updated ..." text in the header using collected_at
function renderHeaderTimestamp(collectedAtIso) {
  const headerStamp = document.getElementById("lastUpdated");
  if (!headerStamp) return;

  const label = timeAgoOrDate(collectedAtIso);
  // if label is "", don't show anything weird, just fallback to time string
  let fallbackTime = "";
  if (collectedAtIso) {
    const d = new Date(collectedAtIso);
    if (!isNaN(d.getTime())) {
      fallbackTime = d.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit"
      });
    }
  }

  if (label) {
    headerStamp.textContent = "Updated " + label;
  } else if (fallbackTime) {
    headerStamp.textContent = "Updated " + fallbackTime;
  } else {
    headerStamp.textContent = "Updated recently";
  }
}

// Build one article card DOM node
function buildCard(article) {
  const card = document.createElement("a");
  card.className = "feed-card";
  card.href = article.url || "#";
  card.target = "_blank";
  card.rel = "noopener noreferrer";

  // top row: source + (optional) age
  const metaRow = document.createElement("div");
  metaRow.className = "feed-meta-row";

  const srcSpan = document.createElement("span");
  srcSpan.className = "feed-source";
  srcSpan.textContent = article.source || "Source";

  const ageSpan = document.createElement("span");
  ageSpan.className = "feed-age";
  const ageText = timeAgoOrDate(article.published || "");
  ageSpan.textContent = ageText || ""; // if "", we just won't show anything
  if (!ageText) {
    ageSpan.style.display = "none";
  }

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

  card.appendChild(metaRow);
  card.appendChild(headlineDiv);
  card.appendChild(snippetDiv);

  return card;
}

// Render all cards into the feed grid
function renderFeed(items, collectedAtIso) {
  const feedGrid = document.getElementById("feedGrid");
  feedGrid.innerHTML = "";

  // show only first 20, like before
  const topItems = items.slice(0, 20);

  // timestamp in header
  renderHeaderTimestamp(collectedAtIso);

  topItems.forEach(article => {
    const card = buildCard(article);
    feedGrid.appendChild(card);
  });
}

(async function init(){
  // NOTE: we changed the JSON schema to include { items: [...], collected_at: "..."}
  const data = await getJSON(
    "static/teams/purdue-mbb/items.json",
    { items: [], collected_at: "" }
  );

  renderFeed(data.items || [], data.collected_at || "");
})();