// ======== CONFIG =========
const ITEMS_URL = "static/teams/purdue-mbb/items.json";
const TEAM_URL = "static/team.json";
const SCHEDULE_URL = "static/schedule.json";
const WIDGETS_URL = "static/widgets.json";

// Tiny transparent fallback (avoids broken images)
const FALLBACK_IMG = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

// ======== LOAD EVERYTHING =========
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const [team, itemsObj, schedule, widgets] = await Promise.all([
      fetchJSON(TEAM_URL),
      fetchJSON(ITEMS_URL),
      fetchJSON(SCHEDULE_URL),
      fetchJSON(WIDGETS_URL)
    ]);

    const items = Array.isArray(itemsObj) ? itemsObj : (itemsObj.items || []);

    renderNav(team.links || []);
    renderBrand(team);
    renderTicker(items);
    renderFeatured(items);
    renderVideos(items);
    renderNews(items);
    renderInsiders(items);
    renderSchedule(schedule);
    renderWidgets(widgets);

    const refreshBtn = document.getElementById("refreshBtn");
    if (refreshBtn) refreshBtn.addEventListener("click", () => location.reload());
  } catch (err) {
    console.error("🚨 Failed to load site data:", err);
  }
});

// ======== HELPERS =========
async function fetchJSON(url) {
  const res = await fetch(url + (url.includes("?") ? "" : "?t=" + Date.now())); // cache-bust
  if (!res.ok) throw new Error(`Failed to load ${url}`);
  return res.json();
}
function truncate(text = "", len = 140) {
  return text.length > len ? text.slice(0, len) + "…" : text;
}
function imgOrFallback(url) {
  if (!url || typeof url !== "string" || url.startsWith("data:")) return FALLBACK_IMG;
  return url;
}
function safeDate(d) {
  if (!d) return "";
  const dt = new Date(d);
  if (String(d).length === 10 && /^\d{4}-\d{2}-\d{2}$/.test(d)) {
    // already YYYY-MM-DD
    return d;
  }
  if (isNaN(dt.getTime())) return String(d).slice(0, 16); // handle "Wed, 24 Se..." gracefully
  return dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ======== NAV / BRAND =========
function renderNav(links) {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  nav.innerHTML = (links || [])
    .map(l => `<a href="${l.href}" target="${String(l.href || "").startsWith('http') ? '_blank' : '_self'}" rel="noopener">${l.label}</a>`)
    .join("");
}
function renderBrand(team) {
  const logo = document.getElementById("logo");
  const word = document.getElementById("wordmark");
  if (logo) logo.src = team.logo || "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Purdue_Boilermakers_wordmark.svg/512px-Purdue_Boilermakers_wordmark.svg.png";
  if (word) word.textContent = team.name || team.wordmark || "Team Hub";
}

// ======== TICKER =========
function renderTicker(items) {
  const track = document.getElementById("tickerTrack");
  if (!track) return;
  const headlines = items
    .filter(i => (i.type || "").toLowerCase() === "news")
    .slice(0, 12)
    .map(i => `<a href="${i.link}" target="_blank" rel="noopener">${i.title || ""}</a>`)
    .join(" • ");
  track.innerHTML = (headlines + " • " + headlines); // repeat for loop
}

// ======== FEATURED =========
function renderFeatured(items) {
  const feature = items.find(i => (i.type || "").toLowerCase() === "news") || items[0];
  if (!feature) return;
  const link = document.getElementById("featureLink");
  const img = document.getElementById("featureImg");
  if (link) link.href = feature.link || "#";
  if (img) img.src = imgOrFallback(feature.image);
  setText("featureSource", feature.source || "");
  setText("featureTrust", (feature.trust || "").replace("_", " "));
  setText("featureTitle", feature.title || "");
  setText("featureSummary", truncate(feature.summary || "", 180));
  setText("featureWhen", safeDate(feature.date));
}
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val || "";
}

// ======== VIDEOS =========
function renderVideos(items) {
  const videos = items.filter(i => (i.type || "").toLowerCase() === "video");
  const container = document.getElementById("videoCarousel");
  if (!container) return;
  container.innerHTML = videos.slice(0, 12).map(v => `
      <a href="${v.link}" class="card video-card" target="_blank" rel="noopener">
        <div class="thumb"><img src="${imgOrFallback(v.image)}" alt="${escapeHtml(v.title || "")}"></div>
        <div class="meta"><span>${v.source || ""}</span> ${v.date ? `• <time>${safeDate(v.date)}</time>` : ""}</div>
        <div class="title">${v.title || ""}</div>
        ${v.summary ? `<div class="summary">${truncate(v.summary, 120)}</div>` : ""}
      </a>
    `).join("");

  const prev = document.getElementById("prevVid");
  const next = document.getElementById("nextVid");
  if (prev) prev.addEventListener("click", () => container.scrollBy({ left: -320, behavior: "smooth" }));
  if (next) next.addEventListener("click", () => container.scrollBy({ left: 320, behavior: "smooth" }));
}

// ======== NEWS GRID =========
function renderNews(items) {
  const news = items.filter(i => (i.type || "").toLowerCase() === "news").slice(0, 24);
  const grid = document.getElementById("newsGrid");
  if (!grid) return;
  grid.innerHTML = news.map(n => `
    <a href="${n.link}" class="card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(n.image)}" alt="${escapeHtml(n.title || "")}"></div>
      <div class="meta"><span>${n.source || ""}</span>${n.date ? ` • <time>${safeDate(n.date)}</time>` : ""}</div>
      <div class="title">${n.title || ""}</div>
      ${n.summary ? `<div class="summary">${truncate(n.summary, 150)}</div>` : ""}
    </a>
  `).join("");
}

// ======== INSIDERS =========
function renderInsiders(items) {
  const insiders = items.filter(i => (i.trust || "").toLowerCase() === "insider" || (i.trust || "").toLowerCase() === "beat");
  const grid = document.getElementById("insiderGrid");
  if (!grid) return;
  grid.innerHTML = insiders.map(n => `
    <a href="${n.link}" class="card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(n.image)}" alt="${escapeHtml(n.title || "")}"></div>
      <div class="meta"><span class="badge">Insider</span> ${n.source || ""}</div>
      <div class="title">${n.title || ""}</div>
      ${n.summary ? `<div class="summary">${truncate(n.summary, 150)}</div>` : ""}
    </a>
  `).join("");
}

// ======== SCHEDULE =========
function renderSchedule(schedule) {
  const list = document.getElementById("scheduleList");
  if (!list || !schedule || !Array.isArray(schedule.games)) return;
  list.innerHTML = schedule.games.map(g => `
    <div class="game-row">
      <strong>${g.opponent}</strong><br>
      <time>${safeDate(g.date)}</time> – <span>${g.venue || ""}</span>
    </div>
  `).join("");
}

// ======== SIDEBAR WIDGETS =========
function renderWidgets(widgets) {
  setText("apRank", (widgets && widgets.ap_rank != null) ? widgets.ap_rank : "—");
  setText("kpRank", (widgets && widgets.kenpom_rank != null) ? widgets.kenpom_rank : "—");
  const nilList = document.getElementById("nilList");
  if (!nilList || !widgets || !Array.isArray(widgets.nil)) return;
  nilList.innerHTML = widgets.nil.map(p => `<li>${(p.name || "")} — ${(p.valuation || "")}</li>`).join("");
}

// ======== ESCAPE =========
function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}