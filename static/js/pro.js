// static/js/pro.js
document.addEventListener("DOMContentLoaded", () => {
  loadTeam();
  loadItems();
  loadSchedule();
  setupRefresh();
});

async function loadTeam() {
  const res = await fetch("/sports-app-project/static/team.json");
  const team = await res.json();
  document.getElementById("wordmark").textContent = team.wordmark || team.team_name;

  const logo = document.getElementById("logo");
  if (logo) logo.src = team.logo_url;

  document.body.style.setProperty("--primary", team.primary_color);
  document.body.style.setProperty("--accent", team.accent);

  setTheme(team);
  renderPromos(team.promos);
}

function setTheme(team) {
  const nav = document.querySelector(".nav");
  nav.innerHTML = "";

  team.links.forEach(link => {
    const a = document.createElement("a");
    a.href = link.href;
    a.textContent = link.label;

    // ✅ open external links in new tab
    if (link.href.startsWith("http")) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }

    nav.appendChild(a);
  });

  const heroImg = document.querySelector(".hero .image");
  if (heroImg) {
    heroImg.style.backgroundImage = `url('${team.hero_image}')`;
  }
}

function renderPromos(promos) {
  const row = document.getElementById("promoRow");
  if (!row) return;
  row.innerHTML = "";

  if (!promos || promos.length === 0) {
    document.getElementById("promos").style.display = "none";
    return;
  }

  promos.forEach(p => {
    const card = document.createElement("div");
    card.className = "promo-card";
    card.innerHTML = `
      <h3>${p.title}</h3>
      <p>${p.text}</p>
      <a href="${p.href}" target="_blank" rel="noopener noreferrer" class="btn">${p.cta}</a>
    `;
    row.appendChild(card);
  });
}

async function loadItems() {
  const res = await fetch("/sports-app-project/static/teams/purdue-mbb/items.json");
  const items = await res.json();

  const feature = items.find(i => i.featured) || items[0];
  if (feature) renderFeature(feature);

  const videos = items.filter(i => i.type === "video");
  const news = items.filter(i => i.type === "news");

  renderVideos(videos);
  renderNews(news);
}

function renderFeature(item) {
  document.getElementById("featureImg").src = item.image_url || "";
  document.getElementById("featureLink").href = item.url;
  document.getElementById("featureTitle").textContent = item.title;
  document.getElementById("featureTitle").href = item.url;
  document.getElementById("featureSummary").textContent = item.summary || "";
  document.getElementById("featureSource").textContent = item.source || "";
  document.getElementById("featureTrust").textContent = item.trust_level || "";
  document.getElementById("featureWhen").textContent = formatTime(item.published_at);
  document.getElementById("featureRead").href = item.url;
}

function renderVideos(videos) {
  const row = document.getElementById("videoRow");
  if (!row) return;
  row.innerHTML = "";

  videos.slice(0, 8).forEach(v => {
    const card = document.createElement("div");
    card.className = "video-card";
    card.innerHTML = `
      <a href="${v.url}" target="_blank" rel="noopener noreferrer" class="thumb">
        <img src="${v.image_url}" alt="${v.title}" loading="lazy" />
      </a>
      <div class="video-meta">
        <h4><a href="${v.url}" target="_blank" rel="noopener noreferrer">${v.title}</a></h4>
        <p class="meta">${v.source} • ${formatTime(v.published_at)}</p>
      </div>
    `;
    row.appendChild(card);
  });
}

function renderNews(news) {
  const grid = document.getElementById("newsGrid");
  if (!grid) return;
  grid.innerHTML = "";

  news.slice(0, 20).forEach(n => {
    const card = document.createElement("div");
    card.className = "news-card";
    card.innerHTML = `
      <a href="${n.url}" target="_blank" rel="noopener noreferrer" class="thumb">
        <img src="${n.image_url}" alt="${n.title}" loading="lazy" />
      </a>
      <div class="news-meta">
        <h4><a href="${n.url}" target="_blank" rel="noopener noreferrer">${n.title}</a></h4>
        <p class="summary">${n.summary || ""}</p>
        <p class="meta">${n.source} • ${formatTime(n.published_at)}</p>
      </div>
    `;
    grid.appendChild(card);
  });
}

async function loadSchedule() {
  const res = await fetch("/sports-app-project/static/schedule.json");
  if (!res.ok) return;
  const schedule = await res.json();
  const list = document.getElementById("scheduleList");
  if (!list) return;

  list.innerHTML = schedule.map(game => `
    <div class="game">
      <div class="date">${formatDate(game.date)}</div>
      <div class="matchup">${game.home ? "vs" : "@"} ${game.opp}</div>
      <div class="time">${game.time_local}</div>
    </div>
  `).join("");
}

function setupRefresh() {
  const btn = document.getElementById("refreshBtn");
  if (btn) {
    btn.addEventListener("click", () => {
      loadItems();
      loadSchedule();
    });
  }
}

function formatTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function formatDate(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
