// static/js/pro.js
// Purdue Men's Basketball News feed rendering

// --- helper: fetch JSON with fallback ---
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

// --- helper: decode HTML entities like &#39; &amp; etc. ---
function decodeEntities(str) {
  if (!str || typeof str !== "string") return "";
  const txt = document.createElement("textarea");
  txt.innerHTML = str;
  // innerText or textContent both work, textContent keeps it safe
  return txt.textContent;
}

// --- helper: format timestamp for each card ---
// We DON'T try to do "2h ago" anymore because you said it's not showing right.
// We just stamp "Oct 27, 2:15 PM" using published or collected_at.
function formatStamp(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  // guard against invalid date
  if (isNaN(dt.getTime())) return "";

  return dt.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

// --- render the top section timestamp "Updated <time>" ---
function renderHeaderTimestamp(items) {
  const updatedEl = document.getElementById("lastUpdated");
  if (!updatedEl) return;

  if (items.length && items[0].collected_at) {
    const stamp = new Date(items[0].collected_at).toLocaleTimeString(
      "en-US",
      {
        hour: "numeric",
        minute: "2-digit"
      }
    );
    updatedEl.textContent = "Updated " + stamp;
  } else {
    updatedEl.textContent = "Updated recently";
  }
}

// --- build each story card ---
function renderFeed(items) {
  const feedGrid = document.getElementById("feedGrid");
  if (!feedGrid) return;

  feedGrid.innerHTML = "";

  // take top 20
  const topItems = items.slice(0, 20);

  // render header timestamp
  renderHeaderTimestamp(topItems);

  topItems.forEach(article => {
    // outer tappable card
    const card = document.createElement("a");
    card.className = "feed-card";
    card.href = article.url || "#";
    card.target = "_blank";
    card.rel = "noopener noreferrer";

    // body wrapper
    const body = document.createElement("div");
    body.className = "feed-body";

    // meta row (source left, time right)
    const metaRow = document.createElement("div");
    metaRow.className = "feed-meta-row";

    const srcSpan = document.createElement("span");
    srcSpan.className = "feed-source";
    srcSpan.textContent = article.source
      ? decodeEntities(article.source)
      : "Source";

    const ageSpan = document.createElement("span");
    ageSpan.className = "feed-age";
    // prefer published, fallback to collected_at
    const ts = formatStamp(article.published || article.collected_at || "");
    ageSpan.textContent = ts;

    metaRow.appendChild(srcSpan);
    metaRow.appendChild(ageSpan);

    // headline
    const headlineDiv = document.createElement("div");
    headlineDiv.className = "feed-headline";
    headlineDiv.textContent = decodeEntities(article.title || "");

    // snippet / subtext
    const snippetDiv = document.createElement("div");
    snippetDiv.className = "feed-snippet";
    snippetDiv.textContent = decodeEntities(article.snippet || "");

    // put it together
    body.appendChild(metaRow);
    body.appendChild(headlineDiv);
    body.appendChild(snippetDiv);

    card.appendChild(body);
    feedGrid.appendChild(card);
  });
}

// --- footer: static trusted Purdue sources list ---
// You told me this disappeared. We’re going to force it back, unchanged,
// and we're NOT trying to be clever about "who actually appeared in feed" here.
function renderFooterSources() {
  const footerListEl = document.getElementById("sourceListStatic");
  if (!footerListEl) return;

  footerListEl.textContent =
    "GoldandBlack.com · On3 Purdue Basketball · 247Sports Purdue Basketball · Purdue Athletics MBB · ESPN Purdue MBB · Yahoo Sports College Basketball · CBS Sports College Basketball · The Field of 68 · SI Purdue Basketball · USA Today Purdue Boilermakers";
}

// --- init ---
(async function init() {
  // pull latest articles JSON
  const data = await getJSON(
    "static/teams/purdue-mbb/items.json",
    { items: [] }
  );

  const stories = Array.isArray(data.items) ? data.items : [];

  renderFeed(stories);          // cards with source + timestamp + decoded text
  renderFooterSources();        // static Purdue-ish source list you want visible
})();