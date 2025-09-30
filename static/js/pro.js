// =====================================
// Team Hub Pro — Frontend Application
// =====================================

// ------- Endpoints -------
const TEAM_URL     = "static/team.json";
const ITEMS_URL    = "static/teams/purdue-mbb/items.json";
const SCHEDULE_URL = "static/schedule.json";
const WIDGETS_URL  = "static/widgets.json";
const INSIDERS_URL = "static/insiders.json";   // new: list of insider resources

// ------- Globals -------
let ALL_ITEMS = [];
let CURRENT_FILTER = null; // one of: insider, official, national, local, null

// Transparent 1x1 fallback (prevents broken image icon)
const FALLBACK_IMG =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

// ------- Boot -------
document.addEventListener("DOMContentLoaded", init);

async function init() {
  try {
    const [team, itemsData, schedule, widgets, insiders] = await Promise.all([
      fetchJSON(TEAM_URL),
      fetchJSON(ITEMS_URL),
      fetchJSON(SCHEDULE_URL),
      fetchJSON(WIDGETS_URL),
      fetchJSON(INSIDERS_URL).catch(() => ({ links: [] })) // tolerate missing
    ]);

    // Unified items array (supports {items:[...]} or [...] shapes)
    ALL_ITEMS = Array.isArray(itemsData) ? itemsData : (itemsData.items || []);

    renderBrand(team);
    renderNav(team.links || []);
    bindRefresh();

    // first render (no filter)
    renderEverything(ALL_ITEMS, schedule, widgets, insiders.links);

    // enable ticker tag filtering (event delegation)
    wireTickerFilter();

    // optional: expose simple hash filter (?tag=insider)
    const url = new URL(location.href);
    const tagParam = (url.searchParams.get("tag") || "").toLowerCase();
    if (["insider","official","national","local"].includes(tagParam)) {
      setFilter(tagParam);
    }
  } catch (err) {
    console.error("Init error:", err);
  }
}

// ------- Rendering Orchestration -------
function renderEverything(items, schedule, widgets, insiderLinks) {
  const filtered = applyFilter(items, CURRENT_FILTER);
  renderTicker(items);                // ticker shows *all* headlines for context
  renderFeatured(filtered, items);    // prefer filtered; fallback to global
  renderVideos(filtered, items);
  renderNews(filtered);
  renderInsiders(filtered, insiderLinks);
  renderSchedule(schedule);
  renderWidgets(widgets);
}

// ------- Helpers -------
async function fetchJSON(url) {
  const res = await fetch(url + (url.includes("?") ? "" : `?t=${Date.now()}`));
  if (!res.ok) throw new Error(`Failed to load ${url}`);
  return res.json();
}
function truncate(txt = "", len = 140) {
  return txt.length > len ? txt.slice(0, len) + "…" : txt;
}
function imgOrFallback(url) {
  return url && typeof url === "string" ? url : FALLBACK_IMG;
}
function safeDate(d) {
  if (!d) return "";
  const dt = new Date(d);
  return isNaN(dt.getTime())
    ? String(d).slice(0, 16)
    : dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function escapeHtml(str) {
  return String(str || "").replace(/[&<>"']/g, (m) => (
    { "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[m]
  ));
}
function bindRefresh() {
  document.getElementById("refreshBtn")?.addEventListener("click", () => location.reload());
}
function isVideoItem(i) {
  const t = (i.type || "").toLowerCase();
  const link = (i.link || "").toLowerCase();
  return t === "video" || link.includes("youtube.com/") || link.includes("youtu.be/");
}
function applyFilter(items, tag) {
  if (!tag) return items;
  return items.filter(i => (i.trust || "").toLowerCase() === tag);
}
function setFilter(tag) {
  CURRENT_FILTER = tag;
  // visual highlight in ticker (active class)
  document.querySelectorAll('.ticker .chip').forEach(ch => {
    ch.classList.toggle('active', (ch.dataset.filter || "") === tag);
  });
  renderEverything(ALL_ITEMS,
    /* schedule */ null, /* widgets */ null, /* insiderLinks */ null
  );
  // Note: schedule/widgets don’t change with filter so we reuse current DOM
}

// ------- Brand / Nav -------
function renderBrand(team) {
  const logo = document.getElementById("logo");
  const word = document.getElementById("wordmark");
  if (logo) logo.src =
    team.logo ||
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Purdue_Boilermakers_wordmark.svg/512px-Purdue_Boilermakers_wordmark.svg.png";
  if (word) word.textContent = team.name || team.wordmark || "Team Hub";
}
function renderNav(links) {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  nav.innerHTML = links.map(l =>
    `<a href="${l.href}" target="${String(l.href).startsWith('http') ? '_blank' : '_self'}" rel="noopener">${l.label}</a>`
  ).join("");
}

// ------- Ticker (clickable chips) -------
function renderTicker(items) {
  const track = document.getElementById("tickerTrack");
  if (!track) return;

  const news = items.filter(i => (i.type || "").toLowerCase() === "news");
  const mk = (i) => {
    const tag = (i.trust || "news").toLowerCase();
    const chip = `<button class="chip" data-filter="${tag}" aria-label="Filter: ${tag}">${tag.toUpperCase()}</button>`;
    return `${chip} <a href="${i.link}" target="_blank" rel="noopener">${escapeHtml(i.title || "")}</a>`;
  };

  const slice = news.slice(0, 18).map(mk).join(" • ");
  track.innerHTML = `${slice} • ${slice} • ${slice}`;
}
function wireTickerFilter() {
  const ticker = document.querySelector(".ticker");
  if (!ticker) return;
  ticker.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    const tag = (btn.dataset.filter || "").toLowerCase();
    setFilter(CURRENT_FILTER === tag ? null : tag); // toggle
  });
}

// ------- Featured (never empty) -------
function renderFeatured(filtered, allItems) {
  const pick = (arr) => arr.find(i => (i.type || "").toLowerCase() === "news");
  // Prefer filtered item with image; then any filtered; then global with image; then any global.
  let f = pick(filtered.filter(i => i.image)) || pick(filtered) ||
          pick(allItems.filter(i => i.image)) || pick(allItems) || null;
  if (!f) return;

  document.getElementById("featureLink").href = f.link || "#";
  document.getElementById("featureImg").src = imgOrFallback(f.image);
  setText("featureSource", f.source || "");
  setText("featureTrust", (f.trust || "").replace("_"," "));
  setText("featureTitle", f.title || "");
  setText("featureSummary", truncate(f.summary || "", 180));
  setText("featureWhen", safeDate(f.date));
}
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? "";
}

// ------- Video Carousel (robust) -------
function renderVideos(filtered, allItems) {
  const videos = filtered.filter(isVideoItem);
  const fallbackVideos = allItems.filter(isVideoItem); // if filter hides all
  const list = videos.length ? videos : fallbackVideos;

  const container = document.getElementById("videoCarousel");
  if (!container) return;

  if (!list.length) {
    container.parentElement.parentElement.style.display = "none"; // hide whole panel
    return;
  } else {
    container.parentElement.parentElement.style.display = "";
  }

  container.innerHTML = list.slice(0, 12).map(v => `
    <a href="${v.link}" class="card video-card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(v.image)}" alt="${escapeHtml(v.title)}"></div>
      <div class="meta"><span>${v.source || ""}</span>${v.date ? ` • <time>${safeDate(v.date)}</time>` : ""}</div>
      <div class="title">${v.title || ""}</div>
      ${v.summary ? `<div class="summary">${truncate(v.summary, 120)}</div>` : ""}
    </a>
  `).join("");

  document.getElementById("prevVid")?.addEventListener("click", () => {
    container.scrollBy({ left: -320, behavior: "smooth" });
  });
  document.getElementById("nextVid")?.addEventListener("click", () => {
    container.scrollBy({ left: 320, behavior: "smooth" });
  });
}

// ------- Headlines -------
function renderNews(items) {
  const news = items.filter(i => (i.type || "").toLowerCase() === "news").slice(0, 24);
  const grid = document.getElementById("newsGrid");
  if (!grid) return;
  grid.innerHTML = news.map(n => `
    <a href="${n.link}" class="card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(n.image)}" alt="${escapeHtml(n.title)}"></div>
      <div class="meta"><span>${n.source || ""}</span>${n.date ? ` • <time>${safeDate(n.date)}</time>` : ""}</div>
      <div class="title">${n.title || ""}</div>
      ${n.summary ? `<div class="summary">${truncate(n.summary, 150)}</div>` : ""}
    </a>
  `).join("");
}

// ------- Insider Coverage -------
function renderInsiders(items, insiderLinks = []) {
  const grid = document.getElementById("insiderGrid");
  if (!grid) return;

  const insiders = items.filter(i => (i.trust || "").toLowerCase() === "insider" || (i.trust || "").toLowerCase() === "beat");

  // Optional “hub” card with fixed insider resources
  const hubCard = insiderLinks?.length
    ? `<div class="card" style="padding:12px">
         <div class="title" style="margin:8px 0">Insider Hub</div>
         <ul class="insider-links">
           ${insiderLinks.map(l => `<li><a href="${l.href}" target="_blank" rel="noopener">${escapeHtml(l.label)}</a></li>`).join("")}
         </ul>
       </div>`
    : "";

  grid.innerHTML = hubCard + insiders.map(n => `
    <a href="${n.link}" class="card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(n.image)}" alt="${escapeHtml(n.title)}"></div>
      <div class="meta"><span class="badge">Insider</span> ${n.source || ""}</div>
      <div class="title">${n.title || ""}</div>
      ${n.summary ? `<div class="summary">${truncate(n.summary, 150)}</div>` : ""}
    </a>
  `).join("");
}

// ------- Sidebar -------
function renderSchedule(schedule) {
  if (!schedule?.games) return;
  const list = document.getElementById("scheduleList");
  if (!list) return;
  list.innerHTML = schedule.games.map(g => `
    <div class="game-row">
      <strong>${g.opponent}</strong><br>
      <time>${safeDate(g.date)}</time> – <span>${g.venue || ""}</span>
    </div>
  `).join("");
}
function renderWidgets(widgets) {
  setText("apRank", widgets?.ap_rank ?? "—");
  setText("kpRank", widgets?.kenpom_rank ?? "—");
  const nilList = document.getElementById("nilList");
  if (!nilList || !Array.isArray(widgets?.nil)) return;
  nilList.innerHTML = widgets.nil.map(p => `<li>${escapeHtml(p.name)} — ${escapeHtml(p.valuation)}</li>`).join("");
}