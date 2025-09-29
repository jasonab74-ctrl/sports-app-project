/* v1.5 — Featured hero, promos, better mobile */

async function loadJSON(path){
  const r = await fetch(path + (path.includes("?") ? "" : "?ts=" + Date.now()), { cache: "no-store" });
  if(!r.ok) throw new Error("HTTP " + r.status + " for " + path);
  return await r.json();
}

/* ----------------------------- THEME ----------------------------- */
function setTheme(t){
  document.documentElement.style.setProperty("--primary",  t.primary_color   || "#004C54");
  document.documentElement.style.setProperty("--secondary",t.secondary_color || "#A5ACAF");
  document.documentElement.style.setProperty("--bg",       t.dark_bg         || "#0a1114");
  document.documentElement.style.setProperty("--panel",    t.light_bg        || "#0f1a1e");

  const hero = document.querySelector(".hero .image");
  if (hero && t.hero_image) hero.style.backgroundImage = `url('${t.hero_image}')`;

  const logo = document.getElementById("logo");
  if (logo && t.logo_url) logo.src = t.logo_url;

  const mark = document.getElementById("wordmark");
  if (mark) mark.textContent = t.wordmark || t.team_name || "Team Hub";

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

function pickFeatured(items){
  // priority: featured:true -> latest non-video -> any item
  const explicit = items.find(i => i.featured === true);
  if (explicit) return explicit;
  const news = items.filter(i => !((i.type||"").toLowerCase().includes("video")));
  if (news.length) return news[0];
  return items[0] || null;
}

function renderFeature(item){
  const FALLBACK = {
    title: "Waiting for first data sync…",
    url: "#",
    summary: "Add items.json with images to see a featured story.",
    source: "Team Hub",
    trust_level: "official",
    published_at: new Date().toISOString(),
    image_url: ""
  };
  const it = item || FALLBACK;
  const img = document.getElementById("featureImg");
  const link = document.getElementById("featureLink");
  const title = document.getElementById("featureTitle");
  const summary = document.getElementById("featureSummary");
  const trust = document.getElementById("featureTrust");
  const src = document.getElementById("featureSource");
  const when = document.getElementById("featureWhen");
  const read = document.getElementById("featureRead");

  if (img) img.src = it.image_url || "";
  if (link) link.href = it.url || "#";
  if (title){ title.textContent = it.title || ""; title.href = it.url || "#"; }
  if (summary) summary.textContent = it.summary || "";
  if (trust) trust.textContent = (it.trust_level || "").replace("_"," ");
  if (src) src.textContent = it.source || "";
  if (when) when.textContent = fmtWhen(it.published_at);
  if (read) read.href = it.url || "#";
}

function renderPromos(theme){
  const host = document.getElementById("promoRow");
  if (!host) return;
  const defaults = [
    {title:"Buy Tickets", text:"Grab seats for upcoming games.", href:"#", cta:"Tickets"},
    {title:"Team Shop", text:"Rep the squad with new gear.", href:"#", cta:"Shop"},
    {title:"Download the App", text:"Scores, alerts, and more.", href:"#", cta:"Get App"}
  ];
  const promos = (theme && theme.promos && theme.promos.length) ? theme.promos : defaults;
  host.innerHTML = promos.map(p => `
    <article class="promo-card">
      <h3 style="margin:0 0 6px 0">${p.title}</h3>
      <p style="margin:0 0 8px 0; color:#cfe7ea">${p.text}</p>
      <div class="promo-cta"><a class="btn" href="${p.href || '#'}" target="_blank" rel="noopener">${p.cta || 'Learn more'}</a></div>
    </article>
  `).join("");
}

function renderLists(items){
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
    console.warn("schedule.json not found (optional)", e.message);
  }
}

/* ----------------------------- MAIN ----------------------------- */
async function main(){
  let theme = { team_slug: "purdue-mbb" };

  // Theme (colors/logo/hero/nav + optional promos)
  try{
    theme = await loadJSON("./static/team.json");
  }catch(e){
    console.warn("Theme load failed (using defaults)", e.message);
  }
  setTheme(theme);
  renderPromos(theme);

  // Items
  let items = [];
  const slug = (theme.team_slug || "purdue-mbb").toLowerCase();
  const itemsPath = `./static/teams/${encodeURIComponent(slug)}/items.json`;
  try{
    items = await loadJSON(itemsPath);
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

  // Featured + lists
  renderFeature(pickFeatured(items));
  renderLists(items);

  // Widgets
  loadSchedule();

  // Social placeholder
  const soc = document.getElementById("socialCol");
  if (soc) soc.innerHTML = `<div class="x-embed">Follow on X: <strong>@${(theme.team_name||'Team').replace(/\s+/g,'')}</strong><br/>Embed live feed here later.</div>`;

  // Refresh button
  const btn = document.getElementById("refreshBtn");
  if (btn) btn.addEventListener("click", () => location.reload());
}

document.addEventListener("DOMContentLoaded", main);
