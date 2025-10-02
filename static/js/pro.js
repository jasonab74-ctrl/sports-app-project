// Team Hub Pro — Purdue build (mobile drawer + ticker + carousel + filters)
const TEAM_URL     = "static/team.json";
const ITEMS_URL    = "static/teams/purdue-mbb/items.json";
const SCHEDULE_URL = "static/schedule.json";
const WIDGETS_URL  = "static/widgets.json";
const INSIDERS_URL = "static/insiders.json";

let ALL_ITEMS = [];
let TEAM_KEYWORDS = [];
let CURRENT_FILTER = "all";

const FALLBACK_IMG = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

document.addEventListener("DOMContentLoaded", init);

async function init(){
  try{
    const [team, itemsData, schedule, widgets, insiders] = await Promise.all([
      fetchJSON(TEAM_URL),
      fetchJSON(ITEMS_URL),
      fetchJSON(SCHEDULE_URL),
      fetchJSON(WIDGETS_URL),
      fetchJSON(INSIDERS_URL).catch(()=>({links:[]}))
    ]);

    TEAM_KEYWORDS = (team.keywords || []).map(s => String(s).toLowerCase());
    ALL_ITEMS = Array.isArray(itemsData) ? itemsData : (itemsData.items || []);

    renderBrand(team);
    buildDrawer(team);
    hydrateStaticLinks(team);
    hydrateSchedule(schedule);
    hydrateInsiders(insiders.links || []);
    hydrateNIL(widgets.nil || []);
    const curated = curateForTeam(ALL_ITEMS);

    renderTicker(curated.slice(0, 12));
    renderCarousel(curated.slice(0, 8));
    renderLists(curated);

    bindFilterBar();
    bindRefresh();
    setSourceCount(widgets.sources || []);
  }catch(e){
    console.error(e);
  }
}

function bindRefresh(){
  if (location.hash === "#refresh") {
    location.hash = "";
    location.reload();
  }
}

function setSourceCount(sources){
  const el = document.getElementById("sourceCount");
  if (!el) return;
  const n = Array.isArray(sources) ? sources.length : 0;
  el.textContent = `Updated • ${n} sources`;
}

function renderBrand(team){
  const logo = document.getElementById("logo");
  const word = document.getElementById("wordmark");
  const dLogo = document.getElementById("drawerLogo");
  const dWord = document.getElementById("drawerWordmark");
  if(logo) logo.src = team.logo || "";
  if(dLogo) dLogo.src = team.logo || "";
  if(word) word.textContent = team.wordmark || team.short_name || team.name;
  if(dWord) dWord.textContent = team.short_name || "Team";
  document.documentElement.style.setProperty("--brand2", team.primary_color || "#000");
  document.documentElement.style.setProperty("--brand", team.secondary_color || "#CEB888");
}

function buildDrawer(team){
  const btn = document.getElementById("mobileMenuBtn");
  const drawer = document.getElementById("mobileDrawer");
  const closeBtn = document.getElementById("drawerClose");
  const nav = document.getElementById("drawerNav");
  const links = team.links || [];
  nav.innerHTML = links.map(l => `<a href="${l.href}" target="${l.href.startsWith('#')?'_self':'_blank'}" rel="noopener">${l.label}</a>`).join("");
  const open = ()=>{ drawer.classList.add("open"); drawer.setAttribute("aria-hidden","false"); btn.setAttribute("aria-expanded","true"); };
  const close = ()=>{ drawer.classList.remove("open"); drawer.setAttribute("aria-hidden","true"); btn.setAttribute("aria-expanded","false"); };
  btn.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  drawer.addEventListener("click", (e)=>{ if(e.target===drawer) close(); });
}

function hydrateStaticLinks(team){
  const ap = document.getElementById("apLink");
  const kp = document.getElementById("kpLink");
  if(ap) ap.href = "https://www.espn.com/mens-college-basketball/rankings";
  if(kp) kp.href = "https://kenpom.com/";
}

function hydrateSchedule(schedule){
  const ul = document.getElementById("scheduleList");
  if(!ul) return;
  (schedule.games || []).slice(0,8).forEach(g=>{
    const when = g.date || "";
    const at = g.home ? "vs" : "@";
    const row = document.createElement("li");
    row.innerHTML = `<span>${when} ${at} ${escapeHTML(g.opponent||"")}</span><span class="muted">${g.time||""}</span>`;
    ul.appendChild(row);
  });
}

function hydrateInsiders(links){
  const ul = document.getElementById("insiderList");
  if(!ul) return;
  ul.innerHTML = links.map(l=>`<li><a href="${l.href}" target="_blank" rel="noopener">${escapeHTML(l.label)}</a><span class="muted">${l.note||""}</span></li>`).join("");
}

function hydrateNIL(list){
  const ol = document.getElementById("nilList");
  if(!ol) return;
  ol.innerHTML = (list||[]).slice(0,5).map(p=>`<li>${escapeHTML(p.name)} — <span class="muted">${p.value}</span></li>`).join("");
}

function bindFilterBar(){
  const bar = document.getElementById("filterBar");
  if(!bar) return;
  bar.addEventListener("click", (e)=>{
    const btn = e.target.closest(".chip");
    if(!btn) return;
    [...bar.querySelectorAll(".chip")].forEach(c=>c.classList.remove("is-active"));
    btn.classList.add("is-active");
    CURRENT_FILTER = btn.dataset.filter || "all";
    renderLists(curateForTeam(ALL_ITEMS));
  });
}

function renderTicker(items){
  const el = document.getElementById("ticker");
  if(!el) return;
  el.innerHTML = items.map(i=>`<span class="tick"><strong>${escapeHTML(i.source)}</strong> — <a href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title)}</a></span>`).join("");
}

function renderCarousel(items){
  const row = document.getElementById("headlineCarousel");
  if(!row) return;
  row.innerHTML = items.map(i=>{
    const img = i.image || FALLBACK_IMG;
    return `<article class="hero-card">
      <img src="${img}" alt="">
      <div class="meta">
        <div class="src"><span class="tag ${i.trust||""}">${i.trust||"source"}</span> ${escapeHTML(i.source||"")}</div>
        <h3><a href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title)}</a></h3>
        <div class="muted">${escapeHTML(i.date||"")}</div>
      </div>
    </article>`;
  }).join("");
}

function renderLists(items){
  const newsList = document.getElementById("newsList");
  const videoList = document.getElementById("videoList");
  if(!newsList || !videoList) return;

  const filtered = items.filter(i=>{
    if(CURRENT_FILTER==="all") return true;
    return (i.trust||"").toLowerCase() === CURRENT_FILTER.toLowerCase();
  });

  const news = filtered.filter(i=>i.type==="news").slice(0,20);
  const vids = filtered.filter(i=>i.type==="video").slice(0,12);

  newsList.innerHTML = news.map(i=>cardHTML(i)).join("");
  videoList.innerHTML = vids.map(i=>cardHTML(i)).join("");
}

function cardHTML(i){
  const img = i.image || FALLBACK_IMG;
  const tag = i.trust ? `<span class="tag ${i.trust}">${i.trust}</span>` : "";
  return `<article class="card">
    <div class="thumb"><img src="${img}" alt=""></div>
    <div class="meta">
      <div class="src">${tag} ${escapeHTML(i.source||"")}</div>
      <h4><a href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title)}</a></h4>
      <div class="muted">${escapeHTML(i.date||"")}</div>
    </div>
  </article>`;
}

function curateForTeam(items){
  if(!Array.isArray(items)) return [];
  const kw = TEAM_KEYWORDS;
  const scored = items.map(i=>{
    const hay = `${(i.title||"")} ${(i.summary||"")}`.toLowerCase();
    let score = 0;
    kw.forEach(k=>{ if(hay.includes(k.toLowerCase())) score+=2; });
    if((i.type||"")==="video") score+=0.5;
    if((i.trust||"")==="official") score+=1;
    return {...i, _score:score};
  });
  return scored.sort((a,b)=>b._score - a._score);
}

async function fetchJSON(url){
  const r = await fetch(url, {cache:"no-store"});
  if(!r.ok) throw new Error(`Failed fetch ${url}`);
  return r.json();
}

function escapeHTML(s){
  return String(s||"")
    .replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;");
}
