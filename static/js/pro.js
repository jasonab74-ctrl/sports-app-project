// ===============================
// Team Hub Pro — Frontend Logic
// Mobile drawer + filtering + robust video/hero
// ===============================

const TEAM_URL     = "static/team.json";
const ITEMS_URL    = "static/teams/purdue-mbb/items.json";
const SCHEDULE_URL = "static/schedule.json";
const WIDGETS_URL  = "static/widgets.json";
const INSIDERS_URL = "static/insiders.json";

let ALL_ITEMS = [];
let CURRENT_FILTER = null;
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

    ALL_ITEMS = Array.isArray(itemsData) ? itemsData : (itemsData.items || []);

    renderBrand(team);
    renderNav(team.links || []);
    setupDrawer(team.links || []);
    bindRefresh();

    renderEverything(ALL_ITEMS, schedule, widgets, insiders.links);

    wireTickerFilter();
  }catch(e){
    console.error("Init failed:", e);
  }
}

function renderEverything(items, schedule, widgets, insiderLinks){
  const filtered = applyFilter(items, CURRENT_FILTER);
  renderTicker(items);
  renderFeatured(filtered, items);
  renderVideos(filtered, items);
  renderNews(filtered);
  renderInsiders(filtered, insiderLinks);
  if (schedule) renderSchedule(schedule);
  if (widgets)  renderWidgets(widgets);
}

async function fetchJSON(url){
  const res = await fetch(url + (url.includes("?") ? "" : `?t=${Date.now()}`));
  if(!res.ok) throw new Error(`Failed to load ${url}`);
  return res.json();
}
function truncate(t="",n=140){return t.length>n?t.slice(0,n)+"…":t}
function imgOrFallback(u){return (u && typeof u==="string")?u:FALLBACK_IMG}
function safeDate(d){
  if(!d) return "";
  const dt = new Date(d);
  return isNaN(dt.getTime()) ? String(d).slice(0,16) :
    dt.toLocaleDateString(undefined,{month:"short",day:"numeric"});
}
function escapeHtml(s){return String(s||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]))}
function isVideoItem(i){
  const t=(i.type||"").toLowerCase(); const l=(i.link||"").toLowerCase();
  return t==="video"||l.includes("youtube.com/")||l.includes("youtu.be/");
}
function applyFilter(items,tag){ if(!tag) return items; return items.filter(i => (i.trust||"").toLowerCase()===tag); }
function setFilter(tag){
  CURRENT_FILTER = tag;
  document.querySelectorAll(".ticker .chip").forEach(ch=>{
    ch.classList.toggle("active", (ch.dataset.filter||"")===tag);
  });
  renderEverything(ALL_ITEMS, null, null, null);
}

function bindRefresh(){
  document.getElementById("refreshBtn")?.addEventListener("click",()=>location.reload());
}

function renderBrand(team){
  const logo=document.getElementById("logo"), word=document.getElementById("wordmark");
  if(logo) logo.src = team.logo || "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Purdue_Boilermakers_wordmark.svg/512px-Purdue_Boilermakers_wordmark.svg.png";
  if(word) word.textContent = team.name || team.wordmark || "Team Hub";
}
function renderNav(links){
  const nav=document.querySelector(".nav");
  if(!nav) return;
  nav.innerHTML = links.map(l=>`<a href="${l.href}" target="${String(l.href).startsWith('http')?'_blank':'_self'}" rel="noopener">${l.label}</a>`).join("");
}

/* ===== Mobile Drawer ===== */
function setupDrawer(links){
  const btn = document.getElementById("mobileMenuBtn");
  const drawer = document.getElementById("mobileDrawer");
  const panel = drawer?.querySelector(".drawer-panel");
  const closeBtn = document.getElementById("drawerClose");
  const backdrop = document.getElementById("drawerBackdrop");
  const mobileNav = document.getElementById("mobileNav");
  const drawerRefresh = document.getElementById("drawerRefresh");

  if (mobileNav) {
    mobileNav.innerHTML = links.map(l=>`<a href="${l.href}" target="${String(l.href).startsWith('http')?'_blank':'_self'}" rel="noopener">${l.label}</a>`).join("");
  }
  const open = () => {
    if(!drawer) return;
    drawer.setAttribute("aria-hidden","false");
    btn?.setAttribute("aria-expanded","true");
    document.body.style.overflow="hidden";
  };
  const close = () => {
    if(!drawer) return;
    drawer.setAttribute("aria-hidden","true");
    btn?.setAttribute("aria-expanded","false");
    document.body.style.overflow="";
  };
  btn?.addEventListener("click", open);
  closeBtn?.addEventListener("click", close);
  backdrop?.addEventListener("click", close);
  panel?.addEventListener("click", e => { e.stopPropagation(); });

  drawerRefresh?.addEventListener("click", ()=>location.reload());
}

/* ===== Ticker (clickable tags) ===== */
function renderTicker(items){
  const track=document.getElementById("tickerTrack");
  if(!track) return;
  const news=items.filter(i => (i.type||"").toLowerCase()==="news");
  const mk=i=>{
    const tag=(i.trust||"news").toLowerCase();
    const chip=`<button class="chip" data-filter="${tag}" aria-label="Filter: ${tag}">${tag.toUpperCase()}</button>`;
    return `${chip} <a href="${i.link}" target="_blank" rel="noopener">${escapeHtml(i.title||"")}</a>`;
  };
  const slice=news.slice(0,18).map(mk).join(" • ");
  track.innerHTML = `${slice} • ${slice} • ${slice}`;
}
function wireTickerFilter(){
  const t=document.querySelector(".ticker");
  if(!t) return;
  t.addEventListener("click",e=>{
    const btn=e.target.closest(".chip");
    if(!btn) return;
    const tag=(btn.dataset.filter||"").toLowerCase();
    setFilter(CURRENT_FILTER===tag?null:tag);
  });
}

/* ===== Featured (never blank) ===== */
function renderFeatured(filtered, all){
  const pickNews = arr => arr.find(i => (i.type||"").toLowerCase()==="news");
  let f = pickNews(filtered.filter(i=>i.image)) || pickNews(filtered) ||
          pickNews(all.filter(i=>i.image)) || pickNews(all) || null;
  if(!f) return;
  document.getElementById("featureLink").href = f.link || "#";
  document.getElementById("featureImg").src = imgOrFallback(f.image);
  setText("featureSource", f.source||"");
  setText("featureTrust", (f.trust||"").replace("_"," "));
  setText("featureTitle", f.title||"");
  setText("featureSummary", truncate(f.summary||"", 160));
  setText("featureWhen", safeDate(f.date));
}
function setText(id,val){const el=document.getElementById(id); if(el) el.textContent=val??""}

/* ===== Videos ===== */
function renderVideos(filtered, all){
  const vids = filtered.filter(isVideoItem);
  const list = vids.length? vids : all.filter(isVideoItem);
  const c = document.getElementById("videoCarousel");
  if(!c) return;

  if(!list.length){
    c.parentElement.parentElement.style.display="none";
    return;
  } else {
    c.parentElement.parentElement.style.display="";
  }

  c.innerHTML = list.slice(0,12).map(v=>`
    <a href="${v.link}" class="card video-card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(v.image)}" alt="${escapeHtml(v.title)}"></div>
      <div class="meta"><span>${v.source||""}</span>${v.date?` • <time>${safeDate(v.date)}</time>`:""}</div>
      <div class="title">${v.title||""}</div>
      ${v.summary?`<div class="summary">${truncate(v.summary,120)}</div>`:""}
    </a>
  `).join("");

  document.getElementById("prevVid")?.addEventListener("click",()=>c.scrollBy({left:-280,behavior:"smooth"}));
  document.getElementById("nextVid")?.addEventListener("click",()=>c.scrollBy({left: 280,behavior:"smooth"}));
}

/* ===== News / Insiders ===== */
function renderNews(items){
  const news=items.filter(i => (i.type||"").toLowerCase()==="news").slice(0,24);
  const grid=document.getElementById("newsGrid");
  if(!grid) return;
  grid.innerHTML = news.map(n=>`
    <a href="${n.link}" class="card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(n.image)}" alt="${escapeHtml(n.title)}"></div>
      <div class="meta"><span>${n.source||""}</span>${n.date?` • <time>${safeDate(n.date)}</time>`:""}</div>
      <div class="title">${n.title||""}</div>
      ${n.summary?`<div class="summary">${truncate(n.summary,150)}</div>`:""}
    </a>
  `).join("");
}
function renderInsiders(items, insiderLinks=[]){
  const grid=document.getElementById("insiderGrid");
  if(!grid) return;

  const insiders = items.filter(i => (i.trust||"").toLowerCase()==="insider" || (i.trust||"").toLowerCase()==="beat");

  const hub = insiderLinks.length ? `
    <div class="card" style="padding:12px">
      <div class="title" style="margin:8px 0">Insider Hub</div>
      <ul class="insider-links">
        ${insiderLinks.map(l=>`<li><a href="${l.href}" target="_blank" rel="noopener">${escapeHtml(l.label)}</a></li>`).join("")}
      </ul>
    </div>` : "";

  grid.innerHTML = hub + insiders.map(n=>`
    <a href="${n.link}" class="card" target="_blank" rel="noopener">
      <div class="thumb"><img src="${imgOrFallback(n.image)}" alt="${escapeHtml(n.title)}"></div>
      <div class="meta"><span class="badge">Insider</span> ${n.source||""}</div>
      <div class="title">${n.title||""}</div>
      ${n.summary?`<div class="summary">${truncate(n.summary,150)}</div>`:""}
    </a>
  `).join("");
}

/* ===== Sidebar ===== */
function renderSchedule(s){
  const list=document.getElementById("scheduleList");
  if(!list || !s?.games) return;
  list.innerHTML = s.games.map(g=>`
    <div class="game-row">
      <strong>${g.opponent}</strong><br>
      <time>${safeDate(g.date)}</time> – <span>${g.venue||""}</span>
    </div>
  `).join("");
}
function renderWidgets(w){
  setText("apRank", w?.ap_rank ?? "—");
  setText("kpRank", w?.kenpom_rank ?? "—");
  const nil=document.getElementById("nilList");
  if(!nil || !Array.isArray(w?.nil)) return;
  nil.innerHTML = w.nil.map(p=>`<li>${escapeHtml(p.name)} — ${escapeHtml(p.valuation)}</li>`).join("");
}