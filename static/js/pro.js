// --- small helpers ---

// Fetch JSON with no caching
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

// Decode HTML entities like &#39; -> ' so titles/snippets read like real language
function decodeEntities(str) {
  if (!str) return "";
  const txt = document.createElement("textarea");
  txt.innerHTML = str;
  return txt.value;
}

// "2h ago", "3d ago", etc. Return "" if we can't parse.
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

// Build a nice canonical key for deduping
// We'll lowercase, decode entities, strip extra spaces.
function canonicalTitle(str) {
  return decodeEntities(str || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

// Dedupe stories by title (first seen wins)
function dedupeByTitle(items) {
  const seen = new Set();
  const out = [];
  for (const art of items) {
    const key = canonicalTitle(art.title);
    if (!key) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(art);
  }
  return out;
}

// --- rendering ---

function renderFeed(items) {
  const feedGrid = document.getElementById("feedGrid");
  const footerSources = document.getElementById("footerSources");
  feedGrid.innerHTML = "";

  // 1) Dedupe repeated headlines
  let cleanedItems = dedupeByTitle(items || []);

  // 2) Limit to top 20 (after dedupe)
  cleanedItems = cleanedItems.slice(0, 20);

  // 3) Update "Updated HH:MM AM/PM" badge in header
  const updatedEl = document.getElementById("lastUpdated");
  if (cleanedItems.length && cleanedItems[0].collected_at) {
    updatedEl.textContent = new Date(cleanedItems[0].collected_at)
      .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } else {
    updatedEl.textContent = "recently";
  }

  // 4) Render each article card (no image block)
  cleanedItems.forEach(article => {
    const card = document.createElement("a");
    card.className = "feed-card";
    card.href = article.url || "#";
    card.target = "_blank";
    card.rel = "noopener noreferrer";

    const body = document.createElement("div");
    body.className = "feed-body feed-body-noimg";

    // meta row
    const metaRow = document.createElement("div");
    metaRow.className = "feed-meta-row";

    const srcSpan = document.createElement("span");
    srcSpan.className = "feed-source";
    srcSpan.textContent = article.source || "Source";

    const ageSpan = document.createElement("span");
    ageSpan.className = "feed-age";
    const relAge = timeAgo(article.published);
    if (relAge !== "") {
      ageSpan.textContent = relAge;
    }

    metaRow.appendChild(srcSpan);
    if (relAge !== "") {
      metaRow.appendChild(ageSpan);
    }

    // headline
    const headlineDiv = document.createElement("div");
    headlineDiv.className = "feed-headline";
    headlineDiv.textContent = decodeEntities(article.title || "");

    // snippet
    const snippetDiv = document.createElement("div");
    snippetDiv.className = "feed-snippet";
    snippetDiv.textContent = decodeEntities(article.snippet || "");

    // assemble
    body.appendChild(metaRow);
    body.appendChild(headlineDiv);
    body.appendChild(snippetDiv);
    card.appendChild(body);

    feedGrid.appendChild(card);
  });

  // 5) Sources footer list: simple and human-readable
  // We gather unique sources from cleanedItems, plus whatever is in our known set
  const knownSources = [
    "GoldandBlack.com",
    "On3 Purdue Basketball",
    "247Sports Purdue Basketball",
    "Purdue Athletics MBB",
    "ESPN Purdue MBB",
    "Yahoo Sports College Basketball",
    "CBS Sports College Basketball",
    "The Field of 68",
    "SI Purdue Basketball",
    "USA Today Purdue Boilermakers"
  ];

  const seenSources = new Set();
  cleanedItems.forEach(a => {
    if (a.source && a.source.trim()) {
      seenSources.add(a.source.trim());
    }
  });

  // Merge: prioritize known (in that nice order), then any extras
  const mergedSources = [];
  knownSources.forEach(src => {
    if (seenSources.has(src)) {
      mergedSources.push(src);
      seenSources.delete(src);
    }
  });
  // add anything else we saw that's not in known list
  seenSources.forEach(src => mergedSources.push(src));

  footerSources.innerHTML = "";
  const label = document.createElement("div");
  label.className = "footer-note-heading";
  label.textContent = "Sources we monitor:";
  footerSources.appendChild(label);

  const list = document.createElement("div");
  list.className = "footer-sources-list";
  list.textContent = mergedSources.join(" · ");
  footerSources.appendChild(list);
}

// --- init ---
(async function init(){
  const data = await getJSON(
    "static/teams/purdue-mbb/items.json",
    { "items": [] }
  );

  renderFeed(data.items || []);
})();