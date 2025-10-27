// --- helpers ---

// Fetch JSON with no caching so we always see latest pipeline output
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

// Decode HTML entities so we don't show &#39; etc.
function decodeEntities(str) {
  if (!str) return "";
  const txt = document.createElement("textarea");
  txt.innerHTML = str;
  return txt.value;
}

// Format ISO date into "Oct 27, 7:12 AM"
function prettyDate(iso) {
  if (!iso) return "";
  const ms = Date.parse(iso);
  if (isNaN(ms)) return "";
  const d = new Date(ms);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

// "2h ago", "3d ago", etc. Return "" if not parseable.
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

// Lowercase, strip whitespace, decode entities → used to dedupe duplicates
function canonicalTitle(str) {
  return decodeEntities(str || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

// Remove duplicate stories by title
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

// We'll bias Purdue-heavy sources to the top (GoldandBlack, On3, etc.)
// and down-rank "generic national chatter".
function sortWithPurdueBias(items) {
  function sourcePriority(src) {
    if (!src) return 0;
    const s = src.toLowerCase();
    // highest priority: true Purdue insiders, official
    if (
      s.includes("goldandblack") ||
      s.includes("on3") ||
      s.includes("247") ||
      s.includes("purdue athletics") ||
      s.includes("si purdue")
    ) return 3;

    // mid priority: national but will specifically mention Purdue sometimes
    if (
      s.includes("espn") ||
      s.includes("cbs") ||
      s.includes("field of 68") ||
      s.includes("field of68") ||
      s.includes("fieldof68")
    ) return 2;

    // lowest: wide-net college basketball feeds (Yahoo, etc.)
    return 1;
  }

  return [...items].sort((a, b) => {
    const ap = sourcePriority(a.source || "");
    const bp = sourcePriority(b.source || "");
    if (ap !== bp) return bp - ap; // higher priority first

    // tie-breaker: newer published first
    const at = Date.parse(a.published || "") || 0;
    const bt = Date.parse(b.published || "") || 0;
    return bt - at;
  });
}

// --- render ---

function renderFeed(items) {
  const feedGrid = document.getElementById("feedGrid");
  const footerSources = document.getElementById("footerSources");
  feedGrid.innerHTML = "";

  // 1. Clean data:
  //    - dedupe identical headlines
  //    - bias order to Purdue-y sources > national > filler
  let cleanedItems = dedupeByTitle(items || []);
  cleanedItems = sortWithPurdueBias(cleanedItems);

  // 2. Limit to top 20
  cleanedItems = cleanedItems.slice(0, 20);

  // 3. Update header "Updated <time>"
  const updatedEl = document.getElementById("lastUpdated");
  if (cleanedItems.length && cleanedItems[0].collected_at) {
    updatedEl.textContent = new Date(cleanedItems[0].collected_at)
      .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } else {
    updatedEl.textContent = "recently";
  }

  // 4. Build feed cards
  cleanedItems.forEach(article => {
    const sourceName = article.source || "Source";
    const publishedIso = article.published || "";
    const friendlyDate = prettyDate(publishedIso); // "Oct 27, 7:12 AM"
    const relAge = timeAgo(publishedIso); // "2h ago"

    const card = document.createElement("a");
    card.className = "feed-card";
    card.href = article.url || "#";
    card.target = "_blank";
    card.rel = "noopener noreferrer";

    const body = document.createElement("div");
    body.className = "feed-body feed-body-noimg";

    // meta row: source on left, published date + "ago" on right
    const metaRow = document.createElement("div");
    metaRow.className = "feed-meta-row";

    const srcSpan = document.createElement("span");
    srcSpan.className = "feed-source";
    srcSpan.textContent = sourceName;

    const rightMeta = document.createElement("span");
    rightMeta.className = "feed-age";
    if (friendlyDate && relAge) {
      rightMeta.textContent = `${friendlyDate} · ${relAge}`;
    } else if (friendlyDate) {
      rightMeta.textContent = friendlyDate;
    } else if (relAge) {
      rightMeta.textContent = relAge;
    } else {
      rightMeta.textContent = ""; // nothing, stays empty
    }

    metaRow.appendChild(srcSpan);
    if (rightMeta.textContent !== "") {
      metaRow.appendChild(rightMeta);
    }

    // headline
    const headlineDiv = document.createElement("div");
    headlineDiv.className = "feed-headline";
    headlineDiv.textContent = decodeEntities(article.title || "");

    // snippet
    const snippetDiv = document.createElement("div");
    snippetDiv.className = "feed-snippet";
    snippetDiv.textContent = decodeEntities(article.snippet || "");

    // assemble the card body
    body.appendChild(metaRow);
    body.appendChild(headlineDiv);
    body.appendChild(snippetDiv);

    // attach to card
    card.appendChild(body);

    // push into DOM
    feedGrid.appendChild(card);
  });

  // 5. Footer sources list
  // Right now, Yahoo is spamming & maybe others haven't posted recently.
  // You asked to always show all sources we track. We'll do that.

  const allSourcesWeTrack = [
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

  footerSources.innerHTML = "";

  const label = document.createElement("div");
  label.className = "footer-note-heading";
  label.textContent = "Sources we monitor:";
  footerSources.appendChild(label);

  const list = document.createElement("div");
  list.className = "footer-sources-list";

  // Join with bullets, but keep them readable on mobile
  list.textContent = allSourcesWeTrack.join(" · ");

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