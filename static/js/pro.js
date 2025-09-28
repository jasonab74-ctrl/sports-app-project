/* static/js/pro.js
 * Pro-style, team-site template JS for GitHub Pages (static only)
 * - Reads theme from ./static/team.json
 * - Reads items from ./static/teams/<team_slug>/items.json
 * - Renders Videos row + News grid
 * - Loads schedule from ./static/schedule.json (if present)
 */

async function loadJSON(path){
  const r = await fetch(path + (path.includes("?") ? "" : "?ts=" + Date.now()), { cache: "no-store" });
  if(!r.ok) throw new Error("HTTP " + r.status + " for " + path);
  return await r.json();
}

/* ----------------------------- THEME ----------------------------- */
function setTheme(t){
  // CSS variables
  document.documentElement.style.setProperty("--primary",  t.primary_color   || "#004C54");
  document.documentElement.style.setProperty("--secondary",t.secondary_color || "#A5ACAF");
  document.documentElement.style.setProperty("--bg",       t.dark_bg         || "#0a1114");
  document.documentElement.style.setProperty("--panel",    t.light_bg        || "#0f1a1e");

  // Hero image
  const hero = document.querySelector(".hero .image");
  if (hero && t.hero_image) hero.style.backgroundImage = `url('${t.hero_image}')`;

  // Logo + wordmark
  const logo = document.getElementById("logo");
  if (logo && t.logo_url) logo.src = t.logo_url;
  const mark = document.getElementById("wordmark");
  if (mark) mark.textContent = t.wordmark || t.team_name || "Team Hub";

  // Top nav links
  const nav = document.querySelector(".nav");
  if (nav) {
    nav.innerHTML = "";
    (t.links || []).forEach(link => {
      const a = document.createElement("a");
      a.href = link.href; a.textContent = link.label;
      nav.appendChild(a);
    });
  }
}

/* ----------------------------- RENDER ----------------------------- */
function fmtWhen(iso){
  if(!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function cardHTML(it){
  const img = it.image_url ? `<img src="${it.image_url}" alt="">` : "";
  const trust = (it.trust_level || "").replace("_"," ");
  const source = it.source || "";
  const when = fmtWhen(it.published_at);

  return `<article class="card">
    <a class="thumb" href="${it.url || "#"}" target="_blank" rel="noopener">${img}</a>
    <div class="meta"><span class="badge">${trust}</span><span>${source}</span>${when?`<span>•</span><time>${when}</time>`:""}</div>
    <a class="title" href="${it.url || "#"}" target="_blank" rel="noopener">${it.title || ""}</a>
    ${it.summary ? `<p class="summary">${it.summary}</p>` : ""}
  </article>`;
}

function render(items){
  const videos = items.filter(i => (i.type || "").toLowerCase().includes("video")).slice(0, 8);
  const news   = items.filter(i => !((i.type || "").toLowerCase().includes("video"))).slice(0, 24);

  const newsGrid = document.getElementById("newsGrid");
  const videoRow = document.getElementById("videoRow");

  if (newsGrid) newsGrid.innerHTML = news.map(cardHTML).join("");

  if (videoRow) {
    videoRow.innerHTML = videos.map(i => `
      <article class="card video-card">
        <a class="thumb" href="${i.url || "#"}" target="_blank" rel="noopener">
          ${i.image_url ? `<img src="${i.image_url}" alt="">` : ""}
        </a>
        <a class="title" href="${i.url || "#"}" target="_blank" rel="noopener">${i.title || ""}</a>
        <div class="meta"><span>${i.source || ""}</span>${i.published_at ? `<span>•</span><time>${fmtWhen(i.published_at)}</time>` : ""}</div>
      </article>
    `).join("");
  }
}

/* ----------------------------- SCHEDULE ----------------------------- */
async function loadSchedule(){
  const host = document.getElementById("scheduleList");
  if (!host) return;
  try{
    const data = await loadJSON("./static/schedule.json");
    host.innerHTML = data.map(g => {
      const date = new Date(g.date);
      const dateTxt = isNaN(date) ? (g.date || "") :
        date.toLocaleDateString(undefined, { month: "short", day: "2-digit" });
      const where = g.home ? "Home" : "Away";
      return `
        <div class="game">
          <div>
            <div class="date">${dateTxt}</div>
            <div class="opp">${g.home ? "" : "@ "}${g.opp || ""}</div>
          </div>
          <div>${where}${g.time_local ? ` • ${g.time_local}` : ""}</div>
        </div>`;
    }).join("");
  }catch(e){
    // Silent if no schedule.json — page still works
    console.warn("schedule.json not found (optional)", e.message);
  }
}

/* ----------------------------- MAIN ----------------------------- */
async function main(){
  let team = { team_slug: "purdue-mbb" };  // default

  // 1) Load theme (colors, hero, nav, logo, and team_slug)
  try{
    team = await loadJSON("./static/team.json");
    window.theme = team;
    setTheme(team);
  }catch(e){
    console.warn("Theme load failed (using defaults)", e.message);
  }

  // 2) Load items for this team
  let items = [];
  const slug = (team.team_slug || "purdue-mbb").toLowerCase();
  const itemsPath = `./static/teams/${encodeURIComponent(slug)}/items.json`;
  try{
    items = await loadJSON(itemsPath);
    // newest first
    items.sort((a,b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));
  }catch(e){
    console.warn("Items load failed, showing placeholder", e.message);
    items = [{
      "type":"news",
      "title":"Waiting for first data sync…",
      "url":"#",
      "summary":"Add static/teams/"+slug+"/items.json or enable the Action to generate it.",
      "published_at": new Date().toISOString(),
      "source":"Team Hub",
      "trust_level":"official",
      "image_url":""
    }];
  }

  // 3) Render content + schedule
  render(items);
  loadSchedule();
}

// Kick off once DOM is ready
document.addEventListener("DOMContentLoaded", main);

// Optional: top-right Refresh button (if present in HTML)
const btn = document.getElementById("refreshBtn");
if (btn) btn.addEventListener("click", () => location.reload());
