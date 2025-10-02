// Team Hub — Purdue build
console.log("[boot] pro.js loaded");
window.addEventListener("error", e => console.error("[js-error]", e.message));
window.addEventListener("unhandledrejection", e => console.error("[promise-reject]", e.reason));

const TEAM_URL     = "static/team.json";
const ITEMS_URL    = "static/teams/purdue-mbb/items.json";
const SCHEDULE_URL = "static/schedule.json";
const WIDGETS_URL  = "static/widgets.json";
const INSIDERS_URL = "static/insiders.json";

let ALL_ITEMS = [];
let TEAM_KEYWORDS = [];
let CURRENT_FILTER = "all";
let CURRENT_VIDEO_FILTER = "all";

const FALLBACK_IMG =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

document.addEventListener("DOMContentLoaded", init);

// Probe to confirm fetch works from the page, not just in a new tab
fetch(WIDGETS_URL, { cache: "no-store" })
  .then(r => r.json())
  .then(j => console.log("[probe] widgets sources:", (j.sources||[]).length))
  .catch(err => console.warn("[probe-fail] widgets.json", err));

async function init(){
  try{
    const [team, itemsData, schedule, widgets, insiders] = await Promise.all([
      fetchJSON(TEAM_URL,     { name:"Purdue", short_name:"Purdue", keywords:["Purdue","Boilermakers"], links:[{label:"News",href:"#news"}] }),
      fetchJSON(ITEMS_URL,    { items: [] }),
      fetchJSON(SCHEDULE_URL, { games: [] }),
      fetchJSON(WIDGETS_URL,  { nil: [], sources: [] }),
      fetchJSON(INSIDERS_URL, { links: [] })
    ]);

    console.log("[counts]", {
      items: Array.isArray(itemsData) ? itemsData.length : (itemsData.items||[]).length,
      sources: (widgets.sources||[]).length
    });

    TEAM_KEYWORDS = (team.keywords || []).map(s => String(s).toLowerCase());
    ALL_ITEMS = Array.isArray(itemsData) ? itemsData : (itemsData.items || []);

    renderBrand(team);
    buildDrawer(team);
    hydrateStaticLinks();
    hydrateSchedule(schedule);
    hydrateInsiders(insiders.links || []);
    hydrateNIL(widgets.nil || []);
    setSourceCount(widgets.sources || []);

    const curated = curateForTeam(ALL_ITEMS);

    renderTicker(curated.slice(0, 12));
    renderCarousel(curated.filter(i=>i.type==="news").slice(0, 8));
    renderNewsList(curated);
    renderVideoList(curated);

    ensureNonEmptyStates(curated);
    bindFilterBars();
    bindModalControls();
  }catch(e){
    console.error(e);
    ensureNonEmptyStates([]);
  }
}

function ensureNonEmptyStates(curated){
  if (!Array.isArray(curated) || curated.length === 0) {
    const n = document.getElementById("newsList");
    const v = document.getElementById("videoList");
    if (n && !n.innerHTML.trim()) n.innerHTML =
      '<div class="body muted">No headlines yet. Try again shortly.</div>';
    if (v && !v.innerHTML.trim()) v.innerHTML =
      '<div class="body muted">No videos yet. Check back soon.</div>';
  }
}

async function fetchJSON(url, fallback = null){
  try{
    const r = await fetch(url, { cache: "no-store" });
    if(!r.ok) throw new Error(`HTTP ${r.status} on ${url}`);
    return await r.json();
  }catch(err){
    console.warn("[fetch-fail]", url, err?.message || err);
    return fallback ?? {};
  }
}

/* UI */
function bindFilterBars(){
  const bar = document.getElementById("filterBar");
  const vbar = document.getElementById("videoFilterBar");
  if(bar){
    bar.addEventListener("click", (e)=>{
      const btn = e.target.closest(".chip");
      if(!btn) return;
      [...bar.querySelectorAll(".chip")].forEach(c=>c.classList.remove("is-active"));
      btn.classList.add("is-active");
      CURRENT_FILTER = btn.dataset.filter || "all";
      renderNewsList(curateForTeam(ALL_ITEMS));
    });
  }
  if(vbar){
    vbar.addEventListener("click", (e)=>{
      const btn = e.target.closest(".chip");
      if(!btn) return;
      [...vbar.querySelectorAll(".chip")].forEach(c=>c.classList.remove("is-active"));
      btn.classList.add("is-active");
      CURRENT_VIDEO_FILTER = btn.dataset.filter || "all";
      renderVideoList(curateForTeam(ALL_ITEMS));
    });
  }
}

function buildDrawer(team){
  const btn = document.getElementById("mobileMenuBtn");
  const drawer = document.getElementById("mobileDrawer");
  const closeBtn = document.getElementById("drawerClose");
  const nav = document.getElementById("drawerNav");
  const links = team.links || [];
  nav.innerHTML = links.map(l => `<a href="${l.href}" target="${l.href.startsWith('#')?'_self':'_blank'}" rel="noopener">${escapeHTML(l.label)}</a>`).join("");
  const open = ()=>{ drawer.classList.add("open"); drawer.setAttribute("aria-hidden","false"); btn.setAttribute("aria-expanded","true"); };
  const close = ()=>{ drawer.classList.remove("open"); drawer.setAttribute("aria-hidden","true"); btn.setAttribute("aria-expanded","false"); };
  btn.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  drawer.addEventListener("click", (e)=>{ if(e.target===drawer) close(); });
}

function bindModalControls(){
  const close = ()=>closeModal();
  document.getElementById("modalClose")?.addEventListener("click", close);
  document.getElementById("modalBackdrop")?.addEventListener("click", close);
  document.addEventListener("keydown", (e)=>{ if(e.key==="Escape") close(); });
}

/* RENDER */
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
      <img src="${img}" alt="" loading="lazy" decoding="async">
      <div class="meta">
        <div class="src"><span class="tag ${i.trust||""}">${i.trust||"source"}</span> ${escapeHTML(i.source||"")}</div>
        <h3><a href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title)}</a></h3>
        <div class="muted">${formatTimeSince(i.date)}</div>
      </div>
    </article>`;
  }).join("");
}

function renderNewsList(items){
  const newsList = document.getElementById("newsList");
  if(!newsList) return;
  const filtered = items.filter(i=>{
    if(i.type!=="news") return false;
    if(CURRENT_FILTER==="all") return true;
    return (i.trust||"").toLowerCase() === CURRENT_FILTER.toLowerCase();
  }).slice(0, 20);
  newsList.innerHTML = filtered.map(i=>cardHTML(i)).join("");
}

function renderVideoList(items){
  const videoList = document.getElementById("videoList");
  if(!videoList) return;
  const vids = items.filter(i=>{
    if(i.type!=="video") return false;
    if(CURRENT_VIDEO_FILTER==="all") return true;
    return (i.trust||"").toLowerCase() === CURRENT_VIDEO_FILTER.toLowerCase();
  }).slice(0, 16);
  videoList.innerHTML = vids.map(v=>videoCardHTML(v)).join("");

  videoList.querySelectorAll("[data-videoid]").forEach(el=>{
    el.addEventListener("click", (e)=>{
      const id = el.getAttribute("data-videoid");
      const link = el.getAttribute("data-link");
      openVideo(id, link);
      e.preventDefault();
    });
  });
}

function cardHTML(i){
  const img = i.image || FALLBACK_IMG;
  const tag = i.trust ? `<span class="tag ${i.trust}">${i.trust}</span>` : "";
  return `<article class="card">
    <div class="thumb"><img src="${img}" alt="" loading="lazy" decoding="async"></div>
    <div class="meta">
      <div class="src">${tag} ${escapeHTML(i.source||"")}</div>
      <h4><a href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title)}</a></h4>
      <div class="muted">${formatTimeSince(i.date)}</div>
    </div>
  </article>`;
}

function videoCardHTML(v){
  const id = v.videoId || deriveYouTubeId(v.link);
  const img = v.image || (id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : FALLBACK_IMG);
  const tag = v.trust ? `<span class="tag ${v.trust}">${v.trust}</span>` : "";
  const duration = v.duration ? `<span class="duration">${formatDuration(v.duration)}</span>` : "";
  return `<article class="card video">
    <a href="${v.link}" class="thumb" data-videoid="${id||""}" data-link="${v.link}">
      <img src="${img}" alt="" loading="lazy" decoding="async">
      ${duration}
      <span class="play">Play</span>
    </a>
    <div class="meta">
      <div class="src">${tag} ${escapeHTML(v.source||"")}</div>
      <h4><a href="${v.link}" target="_blank" rel="noopener">${escapeHTML(v.title)}</a></h4>
      <div class="muted">${formatTimeSince(v.date)}</div>
    </div>
  </article>`;
}

/* Helpers */
function hydrateStaticLinks(){
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
  ul.innerHTML = (links||[]).map(l=>`<li><a href="${l.href}" target="_blank" rel="noopener">${escapeHTML(l.label)}</a><span class="muted">${l.note||""}</span></li>`).join("");
}

function hydrateNIL(list){
  const ol = document.getElementById("nilList");
  if(!ol) return;
  ol.innerHTML = (list||[]).slice(0,5).map(p=>`<li>${escapeHTML(p.name)} — <span class="muted">${p.value}</span></li>`).join("");
}

function setSourceCount(sources){
  const el = document.getElementById("sourceCount");
  if (!el) return;
  const n = Array.isArray(sources) ? sources.length : 0;
  el.textContent = `Updated • ${n} sources`;
}

function escapeHTML(s){
  return String(s||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

function formatTimeSince(dateStr){
  if(!dateStr) return "";
  const now = new Date();
  const dt = new Date(dateStr);
  const sec = Math.max(0, (now - dt) / 1000);
  if (sec < 60) return "just now";
  const m = Math.floor(sec/60); if(m<60) return `${m}m ago`;
  const h = Math.floor(m/60); if(h<24) return `${h}h ago`;
  const d = Math.floor(h/24); if(d<7) return `${d}d ago`;
  return dt.toISOString().slice(0,10);
}

function formatDuration(seconds){
  if (typeof seconds !== "number") return "";
  const m = Math.floor(seconds/60);
  const s = Math.floor(seconds%60);
  return `${m}:${s.toString().padStart(2,"0")}`;
}

function deriveYouTubeId(link){
  try{
    const u = new URL(link);
    if(u.hostname.includes("youtube.com")){
      if(u.pathname === "/watch") return u.searchParams.get("v");
      const m = u.pathname.match(/\/shorts\/([^/]+)/); if(m) return m[1];
    }
    if(u.hostname.includes("youtu.be")){
      const seg = u.pathname.split("/").filter(Boolean)[0];
      return seg || null;
    }
  }catch(e){}
  return null;
}

/* Modal */
function getModal(){
  return { root: document.getElementById("videoModal"), player: document.getElementById("modalPlayer") };
}
function openVideo(videoId, fallbackLink){
  const {root, player} = getModal();
  if(!root || !player) return;
  let src = "";
  if (videoId) src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0`;
  else if (fallbackLink) { window.open(fallbackLink, "_blank", "noopener"); return; }
  player.src = src; root.classList.add("open"); root.setAttribute("aria-hidden","false");
}
function closeModal(){
  const {root, player} = getModal(); if(!root || !player) return;
  player.src = ""; root.classList.remove("open"); root.setAttribute("aria-hidden","true");
}

/* Curation */
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
