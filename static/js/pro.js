/* Core App JS — polished drawer, ticker, carousel, loading states, fallbacks */

const qs = (s, el = document) => el.querySelector(s);
const qsa = (s, el = document) => [...el.querySelectorAll(s)];

const state = {
  teamSlug: new URL(location.href).searchParams.get('team') || 'purdue-mbb',
  items: [],
  team: null,
  widgets: null,
  schedule: null
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

/* ---------- Drawer ---------- */
function initDrawer(){
  const drawer = qs('#drawer');
  const openBtn = qs('#hamburger');
  const closeBtn = qs('#drawer-close');

  const open = () => { drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false'); document.body.classList.add('drawer-open'); };
  const close = () => { drawer.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); document.body.classList.remove('drawer-open'); };

  openBtn.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  drawer.addEventListener('click', e => { if(e.target.matches('a')) close(); });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') close(); });
}

/* ---------- Tabs ---------- */
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
  const list = (items||[]).slice(0,12).map(i=>`<a href="${i.url}" target="_blank" rel="noopener">${decodeEntities(i.title)}</a>`);
  if(!list.length){ ticker.classList.add('hidden'); return; }
  ticker.classList.remove('hidden');
  track.innerHTML = [...list, ...list].join(' • ');
  const totalWidth = track.scrollWidth / 2;
  const duration = Math.max(20, Math.min(60, Math.round(totalWidth / 30)));
  track.style.animation = `marquee ${duration}s linear infinite`;
  let tapped=false;
  ticker.addEventListener('touchstart',()=>{tapped=!tapped; ticker.classList.toggle('tapped',tapped);},{passive:true});
}

/* ---------- Cards / Carousel ---------- */
function makeCard(item){
  const a = document.createElement('a');
  a.className = 'card'; a.href = item.url; a.target = '_blank'; a.rel = 'noopener';

  const thumb = html(`<div class="card__thumb"><img loading="lazy" alt=""></div>`);
  const img = thumb.querySelector('img');
  img.src = item.image || item.thumbnail || '';
  img.alt = decodeEntities(item.title);

  const body = html(`<div class="card__body">
    <div class="card__kicker"></div>
    <div class="card__title"></div>
    <div class="card__meta"></div>
  </div>`);

  body.querySelector('.card__kicker').textContent = item.tag || (item.is_video ? 'Video' : 'News');
  body.querySelector('.card__title').textContent = decodeEntities(item.title);
  const date = item.date ? new Date(item.date) : null;
  const datestr = date ? date.toLocaleDateString(undefined, {month:'short', day:'numeric'}) : '';
  body.querySelector('.card__meta').textContent = [item.source || '', datestr].filter(Boolean).join(' • ');

  a.append(thumb, body);
  return a;
}

function renderCarousel(items){
  const el = qs('#carousel'); el.innerHTML='';
  items.slice(0,8).forEach(i => el.appendChild(makeCard(i)));
  let timer;
  const start = ()=>{ stop(); timer=setInterval(()=>{
    el.scrollBy({left: el.clientWidth * 0.8, behavior:'smooth'});
    if(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4){ el.scrollTo({left:0, behavior:'smooth'}); }
  }, 4500); };
  const stop = ()=> timer && clearInterval(timer);
  el.addEventListener('mouseenter',stop); el.addEventListener('mouseleave',start);
  el.addEventListener('touchstart',stop,{passive:true}); el.addEventListener('touchend',start,{passive:true});
  if(items.length) start();
}

function renderGrid(items, selector){
  const grid = qs(selector); grid.innerHTML='';
  if(!items.length){ grid.innerHTML = `<div class="empty">No items yet — tap <strong>Refresh</strong> to reload.</div>`; return; }
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
  initDrawer(); initTabs();

  // skeletons while loading
  qs('#carousel').innerHTML = `<div class="skel card"></div>`;
  qs('#news-grid').innerHTML = `<div class="skel card"></div><div class="skel card"></div>`;
  qs('#video-grid').innerHTML = `<div class="skel card"></div><div class="skel card"></div>`;

  try{
    // theme
    const teamCfg = await safeJSON(paths.team).then(t => t.teams?.[state.teamSlug] || Object.values(t.teams||{})[0] || {
      name:'Team Hub', logo:'', colors:{accent:'#cfb991', bg:'#0b0f14', card:'#121722'}
    });
    document.title = `${teamCfg.name} — Team Hub`;
    qs('#site-title').textContent = teamCfg.name;
    qs('#drawer-team-name').textContent = teamCfg.name;
    if(teamCfg.logo) qs('#team-logo').src = teamCfg.logo;
    document.documentElement.style.setProperty('--accent', teamCfg.colors.accent);
    document.documentElement.style.setProperty('--bg', teamCfg.colors.bg);
    document.documentElement.style.setProperty('--card', teamCfg.colors.card);

    // data
    const [itemsJson, widgetsAll, scheduleAll] = await Promise.all([
      safeJSON(paths.items(state.teamSlug)),
      safeJSON(paths.widgets),
      safeJSON(paths.schedule)
    ]);

    let items = (itemsJson.items||[]).map(i => ({...i, title: decodeEntities(i.title)}));

    // Fallback demo if empty so the UI never looks blank
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

    renderTicker(items);
    renderCarousel(items.filter(i=>!i.is_video));
    renderGrid(items.filter(i=>!i.is_video), '#news-grid');
    renderGrid(items.filter(i=> i.is_video), '#video-grid');
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
