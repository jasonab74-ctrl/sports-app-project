/* Core App JS — chips only, slim ticker, placeholders, widgets, fade-ins */

const qs = (s, el = document) => el.querySelector(s);
const qsa = (s, el = document) => [...el.querySelectorAll(s)];

const state = {
  teamSlug: new URL(location.href).searchParams.get('team') || 'purdue-mbb'
};

const paths = {
  team: 'static/team.json',
  items: (slug) => `static/teams/${slug}/items.json`,
  widgets: 'static/widgets.json',
  schedule: 'static/schedule.json'
};

/* ---------- Utilities ---------- */
function decodeEntities(str){ if(!str) return ''; const t = document.createElement('textarea'); t.innerHTML = str; return t.value; }
function html(str){ const d=document.createElement('div'); d.innerHTML=str.trim(); return d.firstChild; }
function safeJSON(url){ return fetch(url,{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})); }

/* ---------- Tabs (primary nav) ---------- */
function initTabs(){
  qsa('.tabs .chip').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      qsa('.tabs .chip').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      qsa('.tab').forEach(sec=>sec.classList.remove('visible'));
      qs('#'+tab).classList.add('visible');
    });
  });
}

/* ---------- Ticker ---------- */
function renderTicker(items){
  const ticker = qs('#ticker');
  const track = qs('#ticker-track');
  const list = (items||[]).slice(0,16).map(i=>`<a href="${i.url}" target="_blank" rel="noopener">${decodeEntities(i.title)}</a>`);
  if(!list.length){ ticker.classList.add('hidden'); return; }
  ticker.classList.remove('hidden');
  track.innerHTML = [...list, ...list].join(' • ');
  const totalWidth = track.scrollWidth / 2;
  const duration = Math.max(22, Math.min(55, Math.round(totalWidth / 32))); // seconds
  track.style.animation = `marquee ${duration}s linear infinite`;
}

/* ---------- Card factory ---------- */
const FALLBACK_SVG = encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675">
  <defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
    <stop stop-color="#101726" offset="0"/><stop stop-color="#0d1423" offset="1"/></linearGradient></defs>
  <rect fill="url(#g)" width="1200" height="675"/>
  <text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle" fill="#415070" font-family="system-ui,Segoe UI,Roboto" font-size="42">Sports App Project</text>
</svg>`);

function makeCard(item){
  const a = document.createElement('a');
  a.className = 'card fade-in'; a.href = item.url || '#'; a.target = '_blank'; a.rel = 'noopener';

  const thumb = html(`<div class="card__thumb"><img loading="lazy" alt=""></div>`);
  const img = thumb.querySelector('img');
  const src = item.image || item.thumbnail || `data:image/svg+xml;charset=utf-8,${FALLBACK_SVG}`;
  if(!item.image && !item.thumbnail) thumb.classList.add('placeholder');
  img.src = src;
  img.alt = decodeEntities(item.title || '');

  const body = html(`<div class="card__body">
    <div class="card__kicker"></div>
    <div class="card__title"></div>
    <div class="card__meta"></div>
  </div>`);

  body.querySelector('.card__kicker').textContent = item.tag || (item.is_video ? 'Video' : 'News');
  body.querySelector('.card__title').textContent = decodeEntities(item.title || '');
  const d = item.date ? new Date(item.date) : null;
  const datestr = d ? d.toLocaleDateString(undefined, {month:'short', day:'numeric'}) : '';
  body.querySelector('.card__meta').textContent = [item.source || '', datestr].filter(Boolean).join(' • ');

  a.append(thumb, body);
  return a;
}

/* ---------- Renders ---------- */
function renderCarousel(items){
  const el = qs('#carousel'); el.innerHTML='';
  items.slice(0,8).forEach(i => el.appendChild(makeCard(i)));
  let timer;
  const start = ()=>{ stop(); if(!items.length) return; timer=setInterval(()=>{
    el.scrollBy({left: el.clientWidth * 0.8, behavior:'smooth'});
    if(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4){ el.scrollTo({left:0, behavior:'smooth'}); }
  }, 4500); };
  const stop = ()=> timer && clearInterval(timer);
  el.addEventListener('mouseenter',stop); el.addEventListener('mouseleave',start);
  el.addEventListener('touchstart',stop,{passive:true}); el.addEventListener('touchend',start,{passive:true});
  start();
}

function renderGrid(items, selector){
  const grid = qs(selector); grid.innerHTML='';
  if(!items.length){ grid.innerHTML = `<div class="empty">No items yet — add feeds in <code>static/sources.json</code> and run the collector.</div>`; return; }
  items.slice(0,24).forEach(i => grid.appendChild(makeCard(i)));
}

/* ---------- Widgets ---------- */
function renderRankings(w){
  const el = qs('#rankings-body'); el.innerHTML='';
  const rows = [
    ['AP Rank', w?.ap_rank ?? '—'],
    ['KenPom',  w?.kenpom  ?? '—'],
    ['NET',     w?.net     ?? '—']
  ];
  const ul = document.createElement('ul'); ul.className='list';
  rows.forEach(([k,v])=>{ const li=document.createElement('li'); li.innerHTML=`<span>${k}</span><strong>${v}</strong>`; ul.appendChild(li); });
  el.appendChild(ul);
}
function renderSchedule(sch){
  const el = qs('#schedule-body'); el.innerHTML='';
  const games = sch?.games || [];
  const now = new Date();
  const upcoming = games.filter(g => new Date(g.date) >= now).sort((a,b)=>new Date(a.date)-new Date(b.date)).slice(0,6);
  if(!upcoming.length){ el.innerHTML = `<div class="empty">No upcoming games.</div>`; return; }
  const ul = document.createElement('ul'); ul.className='list';
  upcoming.forEach(g=>{
    const d = new Date(g.date);
    const left = `${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}`;
    const right = g.venue || (g.home ? 'Home' : 'Away');
    const li = document.createElement('li'); li.innerHTML = `<span>${left}</span><span>${right}</span>`;
    ul.appendChild(li);
  });
  el.appendChild(ul);
}
function renderNIL(w){
  const el=qs('#nil-body'); el.innerHTML='';
  const list=(w?.nil)||[];
  if(!list.length){ el.innerHTML=`<div class="empty">NIL data not available.</div>`; return; }
  const ul=document.createElement('ul'); ul.className='list';
  list.slice(0,5).forEach(p=>{ const li=document.createElement('li'); li.innerHTML=`<span>${p.name}</span><span>${p.value}</span>`; ul.appendChild(li); });
  el.appendChild(ul);
}
function renderInsider(w){
  const el=qs('#insider-body'); el.innerHTML='';
  const links=(w?.insider)||[];
  if(!links.length){ el.innerHTML=`<div class="empty">Add insider links in <code>static/widgets.json</code>.</div>`; return; }
  const ul = document.createElement('ul'); ul.className='list';
  links.forEach(l=>{ const li=document.createElement('li'); li.innerHTML=`<a href="${l.url}" target="_blank" rel="noopener">${l.name}</a><span>${l.note||''}</span>`; ul.appendChild(li); });
  el.appendChild(ul);
}

/* ---------- Boot ---------- */
async function boot(){
  initTabs();

  // Skeletons while loading
  qs('#carousel').innerHTML = `<div class="skel card"></div>`;
  qs('#news-grid').innerHTML = `<div class="skel card"></div><div class="skel card"></div>`;
  qs('#video-grid').innerHTML = `<div class="skel card"></div><div class="skel card"></div>`;

  try{
    // Theme
    const teamCfg = await safeJSON(paths.team).then(t => t.teams?.[state.teamSlug] || Object.values(t.teams||{})[0] || {
      name:'Team Hub', logo:'', colors:{accent:'#cfb991', bg:'#0b0f14', card:'#121722'}
    });
    document.title = `${teamCfg.name} — Team Hub`;
    qs('#site-title').textContent = teamCfg.name;
    if(teamCfg.logo) qs('#team-logo').src = teamCfg.logo;
    document.documentElement.style.setProperty('--accent', teamCfg.colors.accent);
    document.documentElement.style.setProperty('--bg', teamCfg.colors.bg);
    document.documentElement.style.setProperty('--card', teamCfg.colors.card);

    // Data
    const [itemsJson, widgetsAll, scheduleAll] = await Promise.all([
      safeJSON(paths.items(state.teamSlug)),
      safeJSON(paths.widgets),
      safeJSON(paths.schedule)
    ]);

    let items = (itemsJson.items||[]).map(i => ({...i, title: decodeEntities(i.title)}));
    if(!items.length){
      items = [{
        title:'Welcome to your Team Hub — connect feeds to populate live content',
        url:'#',
        image:'',
        thumbnail:'',
        source:'Sports App Project',
        date:new Date().toISOString(),
        tag:'News',
        is_video:false
      }];
    }
    const widgets = widgetsAll[state.teamSlug] || widgetsAll.default || {};
    const schedule = scheduleAll[state.teamSlug] || scheduleAll;

    // Split
    const news = items.filter(i=>!i.is_video);
    const vids = items.filter(i=> i.is_video);

    renderTicker(items);
    renderCarousel(news.length?news:items);
    renderGrid(news.length?news:items, '#news-grid');
    renderGrid(vids, '#video-grid');
    renderRankings(widgets);
    renderSchedule(schedule);
    renderNIL(widgets);
    renderInsider(widgets);

  }catch(err){
    console.error(err);
    qs('#news-grid').innerHTML = `<div class="empty">Couldn’t load data. Check your JSON paths and try again.</div>`;
  }

  qs('#refresh').addEventListener('click', ()=>location.reload());
}

document.addEventListener('DOMContentLoaded', boot);
