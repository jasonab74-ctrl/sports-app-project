// ======== CONFIG =========
const ITEMS_URL = "static/teams/purdue-mbb/items.json";
const TEAM_URL = "static/team.json";
const SCHEDULE_URL = "static/schedule.json";
const WIDGETS_URL = "static/widgets.json";

// ======== LOAD EVERYTHING =========
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const [team, items, schedule, widgets] = await Promise.all([
      fetchJSON(TEAM_URL),
      fetchJSON(ITEMS_URL),
      fetchJSON(SCHEDULE_URL),
      fetchJSON(WIDGETS_URL)
    ]);

    renderNav(team.links);
    renderBrand(team);
    renderTicker(items);
    renderFeatured(items);
    renderVideos(items);
    renderNews(items);
    renderInsiders(items);
    renderSchedule(schedule);
    renderWidgets(widgets);

  } catch (err) {
    console.error("🚨 Failed to load site data:", err);
  }
});

// ======== HELPERS =========
async function fetchJSON(url) {
  const res = await fetch(url + "?t=" + Date.now()); // cache-bust
  if (!res.ok) throw new Error(`Failed to load ${url}`);
  return res.json();
}

function truncate(text, len = 140) {
  return text.length > len ? text.slice(0, len) + "…" : text;
}

// ======== NAV =========
function renderNav(links) {
  const nav = document.querySelector(".nav");
  nav.innerHTML = links
    .map(l => `<a href="${l.href}" target="${l.href.startsWith('http') ? '_blank' : '_self'}">${l.label}</a>`)
    .join("");
}

function renderBrand(team) {
  document.getElementById("logo").src = team.logo;
  document.getElementById("wordmark").textContent = team.name;
}

// ======== TICKER =========
function renderTicker(items) {
  const ticker = document.getElementById("tickerTrack");
  const headlines = items
    .filter(i => i.type === "news")
    .slice(0, 10)
    .map(i => `<a href="${i.link}" target="_blank">${i.title}</a>`)
    .join(" • ");
  ticker.innerHTML = headlines.repeat(3); // repeat for infinite scroll
}

// ======== FEATURED =========
function renderFeatured(items) {
  const feature = items.find(i => i.type === "news");
  if (!feature) return;
  document.getElementById("featureLink").href = feature.link;
  document.getElementById("featureImg").src = feature.image || "static/placeholder.jpg";
  document.getElementById("featureSource").textContent = feature.source || "";
  document.getElementById("featureTrust").textContent = feature.trust || "";
  document.getElementById("featureTitle").textContent = feature.title;
  document.getElementById("featureSummary").textContent = truncate(feature.summary || "", 180);
  document.getElementById("featureWhen").textContent = feature.date || "";
}

// ======== VIDEOS =========
function renderVideos(items) {
  const videos = items.filter(i => i.type === "video");
  const container = document.getElementById("videoCarousel");
  container.innerHTML = videos
    .slice(0, 12)
    .map(v => `
      <div class="card video-card">
        <div class="thumb"><img src="${v.image}" alt="${v.title}"></div>
        <div class="meta"><span>${v.source}</span></div>
        <div class="title">${v.title}</div>
      </div>
    `).join("");

  document.getElementById("prevVid").addEventListener("click", () => {
    container.scrollBy({ left: -300, behavior: "smooth" });
  });
  document.getElementById("nextVid").addEventListener("click", () => {
    container.scrollBy({ left: 300, behavior: "smooth" });
  });
}

// ======== NEWS GRID =========
function renderNews(items) {
  const news = items.filter(i => i.type === "news").slice(0, 20);
  const grid = document.getElementById("newsGrid");
  grid.innerHTML = news.map(n => `
    <a href="${n.link}" class="card" target="_blank">
      <div class="thumb"><img src="${n.image}" alt="${n.title}"></div>
      <div class="meta"><span>${n.source}</span> • <time>${n.date}</time></div>
      <div class="title">${n.title}</div>
      <div class="summary">${truncate(n.summary, 150)}</div>
    </a>
  `).join("");
}

// ======== INSIDERS =========
function renderInsiders(items) {
  const insiders = items.filter(i => i.trust === "insider");
  const grid = document.getElementById("insiderGrid");
  grid.innerHTML = insiders.map(n => `
    <a href="${n.link}" class="card" target="_blank">
      <div class="thumb"><img src="${n.image}" alt="${n.title}"></div>
      <div class="meta"><span class="badge">Insider</span> ${n.source}</div>
      <div class="title">${n.title}</div>
      <div class="summary">${truncate(n.summary, 150)}</div>
    </a>
  `).join("");
}

// ======== SCHEDULE =========
function renderSchedule(schedule) {
  const list = document.getElementById("scheduleList");
  list.innerHTML = schedule.games.map(g => `
    <div class="game-row">
      <strong>${g.opponent}</strong><br>
      <time>${g.date}</time> – <span>${g.venue}</span>
    </div>
  `).join("");
}

// ======== SIDEBAR WIDGETS =========
function renderWidgets(widgets) {
  document.getElementById("apRank").textContent = widgets.ap_rank || "—";
  document.getElementById("kpRank").textContent = widgets.kenpom_rank || "—";
  const nilList = document.getElementById("nilList");
  nilList.innerHTML = widgets.nil
    .map(p => `<li>${p.name} — ${p.valuation}</li>`)
    .join("");
}

// ======== REFRESH =========
document.getElementById("refreshBtn").addEventListener("click", () => {
  location.reload();
});