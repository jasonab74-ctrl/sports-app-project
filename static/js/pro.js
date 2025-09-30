// ===============================
// Team Hub Pro — Frontend Logic
// ===============================

// ----------- CONFIG -----------
const ITEMS_URL = "static/teams/purdue-mbb/items.json";
const TEAM_URL = "static/team.json";
const SCHEDULE_URL = "static/schedule.json";
const WIDGETS_URL = "static/widgets.json";

// Transparent fallback image (prevents broken thumbs)
const FALLBACK_IMG =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

// ------------------------------
// INIT
// ------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const [team, itemsData, schedule, widgets] = await Promise.all([
      fetchJSON(TEAM_URL),
      fetchJSON(ITEMS_URL),
      fetchJSON(SCHEDULE_URL),
      fetchJSON(WIDGETS_URL),
    ]);

    const items = Array.isArray(itemsData) ? itemsData : itemsData.items || [];

    renderBrand(team);
    renderNav(team.links || []);
    renderTicker(items);
    renderFeatured(items);
    renderVideos(items);
    renderNews(items);
    renderInsiders(items);
    renderSchedule(schedule);
    renderWidgets(widgets);

    document
      .getElementById("refreshBtn")
      ?.addEventListener("click", () => location.reload());
  } catch (e) {
    console.error("🚨 Failed to initialize:", e);
  }
});

// ------------------------------
// FETCH HELPERS
// ------------------------------
async function fetchJSON(url) {
  const res = await fetch(`${url}?t=${Date.now()}`); // cache-bust
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

// ------------------------------
// BRAND & NAV
// ------------------------------
function renderBrand(team) {
  const logo = document.getElementById("logo");
  const word = document.getElementById("wordmark");
  if (logo)
    logo.src =
      team.logo ||
      "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Purdue_Boilermakers_wordmark.svg/512px-Purdue_Boilermakers_wordmark.svg.png";
  if (word) word.textContent = team.name || team.wordmark || "Team Hub";
}

function renderNav(links) {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  nav.innerHTML = links
    .map(
      (l) =>
        `<a href="${l.href}" target="${
          l.href.startsWith("http") ? "_blank" : "_self"
        }">${l.label}</a>`
    )
    .join("");
}

// ------------------------------
// TICKER
// ------------------------------
function renderTicker(items) {
  const track = document.getElementById("tickerTrack");
  if (!track) return;

  const headlines = items
    .filter((i) => (i.type || "").toLowerCase() === "news")
    .slice(0, 14)
    .map(
      (i) =>
        `<span class="chip">${(i.trust || "NEWS").toUpperCase()}</span> <a href="${
          i.link
        }" target="_blank" rel="noopener">${i.title || ""}</a>`
    )
    .join(" • ");

  track.innerHTML = `${headlines} • ${headlines} • ${headlines}`;
}

// ------------------------------
// FEATURED STORY
// ------------------------------
function renderFeatured(items) {
  const feature = items.find((i) => i.type === "news") || items[0];
  if (!feature) return;

  document.getElementById("featureLink").href = feature.link || "#";
  document.getElementById("featureImg").src = imgOrFallback(feature.image);
  setText("featureSource", feature.source || "");
  setText("featureTrust", (feature.trust || "").replace("_", " "));
  setText("featureTitle", feature.title || "");
  setText("featureSummary", truncate(feature.summary || "", 180));
  setText("featureWhen", safeDate(feature.date));
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ------------------------------
// VIDEO CAROUSEL
// ------------------------------
function renderVideos(items) {
  const videos = items.filter((i) => (i.type || "").toLowerCase() === "video");
  const container = document.getElementById("videoCarousel");
  if (!container) return;

  container.innerHTML = videos
    .slice(0, 12)
    .map(
      (v) => `
      <a href="${v.link}" class="card video-card" target="_blank" rel="noopener">
        <div class="thumb"><img src="${imgOrFallback(
          v.image
        )}" alt="${escapeHtml(v.title)}"></div>
        <div class="meta"><span>${v.source || ""}</span>${
        v.date ? ` • <time>${safeDate(v.date)}</time>` : ""
      }</div>
        <div class="title">${v.title || ""}</div>
        ${
          v.summary
            ? `<div class="summary">${truncate(v.summary, 120)}</div>`
            : ""
        }
      </a>`
    )
    .join("");

  document
    .getElementById("prevVid")
    ?.addEventListener("click", () =>
      container.scrollBy({ left: -320, behavior: "smooth" })
    );
  document
    .getElementById("nextVid")
    ?.addEventListener("click", () =>
      container.scrollBy({ left: 320, behavior: "smooth" })
    );
}

// ------------------------------
// NEWS & INSIDERS
// ------------------------------
function renderNews(items) {
  const news = items.filter((i) => (i.type || "").toLowerCase() === "news");
  const grid = document.getElementById("newsGrid");
  if (!grid) return;

  grid.innerHTML = news
    .slice(0, 24)
    .map(
      (n) => `
      <a href="${n.link}" class="card" target="_blank" rel="noopener">
        <div class="thumb"><img src="${imgOrFallback(
          n.image
        )}" alt="${escapeHtml(n.title)}"></div>
        <div class="meta"><span>${n.source || ""}</span>${
        n.date ? ` • <time>${safeDate(n.date)}</time>` : ""
      }</div>
        <div class="title">${n.title || ""}</div>
        ${
          n.summary
            ? `<div class="summary">${truncate(n.summary, 150)}</div>`
            : ""
        }
      </a>`
    )
    .join("");
}

function renderInsiders(items) {
  const insiders = items.filter(
    (i) =>
      (i.trust || "").toLowerCase() === "insider" ||
      (i.trust || "").toLowerCase() === "beat"
  );
  const grid = document.getElementById("insiderGrid");
  if (!grid) return;

  grid.innerHTML = insiders
    .map(
      (n) => `
      <a href="${n.link}" class="card" target="_blank" rel="noopener">
        <div class="thumb"><img src="${imgOrFallback(
          n.image
        )}" alt="${escapeHtml(n.title)}"></div>
        <div class="meta"><span class="badge">Insider</span> ${
        n.source || ""
      }</div>
        <div class="title">${n.title || ""}</div>
        ${
          n.summary
            ? `<div class="summary">${truncate(n.summary, 150)}</div>`
            : ""
        }
      </a>`
    )
    .join("");
}

// ------------------------------
// SCHEDULE & WIDGETS
// ------------------------------
function renderSchedule(schedule) {
  const list = document.getElementById("scheduleList");
  if (!list || !schedule?.games) return;

  list.innerHTML = schedule.games
    .map(
      (g) => `
    <div class="game-row">
      <strong>${g.opponent}</strong><br>
      <time>${safeDate(g.date)}</time> – <span>${g.venue || ""}</span>
    </div>`
    )
    .join("");
}

function renderWidgets(widgets) {
  setText("apRank", widgets?.ap_rank ?? "—");
  setText("kpRank", widgets?.kenpom_rank ?? "—");

  const nilList = document.getElementById("nilList");
  if (!nilList || !Array.isArray(widgets?.nil)) return;

  nilList.innerHTML = widgets.nil
    .map((p) => `<li>${p.name} — ${p.valuation}</li>`)
    .join("");
}

// ------------------------------
// UTIL
// ------------------------------
function escapeHtml(str) {
  return String(str || "").replace(/[&<>"']/g, (m) => {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[
      m
    ];
  });
}
