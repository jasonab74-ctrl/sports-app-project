/* App JS v1.9 — working tabs, featured carousel, search, quick links, schedule states, footer health */

const qs  = (s, el=document) => el.querySelector(s);
const qsa = (s, el=document) => [...el.querySelectorAll(s)];

const state = {
  teamSlug: new URL(location.href).searchParams.get('team') || 'purdue-mbb',
  items: [],
  searchTerm: ''
};

const paths = {
  team:     'static/team.json',
  items:    (slug) => `static/teams/${slug}/items.json`,
  widgets:  'static/widgets.json',
  schedule: 'static/schedule.json'
};

function decodeEntities(str){ if(!str) return ''; const t=document.createElement('textarea'); t.innerHTML=str; return t.value; }
function safeJSON(url){ return fetch(url,{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})); }

/* ---------- helpers ---------- */
function initTabs(){
  // Ensure default visible
  qsa('.tab').forEach(sec => sec.classList.remove('visible'));
  qs('#news')?.classList.add('visible');
  qsa('.tabs .chip').forEach(b => b.classList.remove('active'));
  qs('#tab-news')?.classList.add('active');

  qsa('.tabs .chip').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const tab=btn.dataset.tab;
      qsa('.tabs .chip').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      qsa('.tab').forEach(sec=>sec.classList.remove('visible'));
      const active = qs('#'+tab);
      if (active) active.classList.add('visible');
      // scroll to content top on mobile
      const y = qs('#content')?.getBoundingClientRect().top + window.scrollY - 8;
      if (Number.isFinite(y)) window.scrollTo({top:y, behavior:'smooth'});
    }, {passive:true});
  });
}

function initSearch(){
  const box=document.createElement('input');
  box.type='search';
  box.placeholder='Search news & videos…';
  box.className='search-box';
  qs('.tabs').before(box);
  box.addEventListener('input',()=>{ state.searchTerm=(box.value||'').toLowerCase(); renderAll(); });
}

function renderTicker(items){
  const ticker=qs('#ticker'), track=qs('#ticker-track');
  const list=(items||[]).filter(i=>i.url&&i.title).slice(0,18).map(i=>`<a href="${i.url}" target="_blank" rel="noopener">${decodeEntities(i.title)}</a>`);
  if(list.length<3){ticker.classList.add('hidden');return;}
  ticker.classList.remove('hidden'); track.innerHTML=[...list,...list].join(' • ');
  const dur=Math.max(22,Math.min(55,Math.round(track.scrollWidth/64)));
  track.style.animation=`marquee ${dur}s linear infinite`;
}

/* ---------- card helpers ---------- */
const FALLBACK_NEWS = 'static/img/fallback-news.svg';

function prettySource(src){
  if(!src) return '';
  const s=(src||'').toLowerCase();
  if(s.includes('boilerball')) return 'BoilerBall';
  if(s.includes('purduesports')) return 'Purdue Athletics';
  if(s.includes('hammerandrails')) return 'Hammer & Rails';
  if(s.includes('goldandblack')) return 'GoldandBlack';
  if(s.includes('on3.com')) return 'On3';
  if(s.includes('si.com')) return 'Sports Illustrated';
  if(s.includes('youtube')) return 'YouTube';
  return src.replace(/^www\./,'');
}
function formatDuration(sec){
  sec = Number(sec||0); if(!sec) return '';
  const h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), s=sec%60;
  return h?`${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${m}:${String(s).padStart(2,'0')}`;
}
function isYouTube(u){ u=(u||'').toLowerCase(); return u.includes('youtube.com')||u.includes('youtu.be'); }

function makeCard(item){
  const a=document.createElement('a'); a.className='card'; a.href=item.url||'#'; a.target='_blank'; a.rel='noopener';
  const thumb=document.createElement('div'); thumb.className='card__thumb';
  const img=document.createElement('img'); img.loading='lazy'; img.decoding='async';
  img.src=item.image||item.thumbnail||FALLBACK_NEWS;
  img.alt=(item.title||'').replace(/<[^>]+>/g,'');
  img.onerror=()=>{ img.src=FALLBACK_NEWS; thumb.classList.add('placeholder'); };
  thumb.appendChild(img);

  const body=document.createElement('div'); body.className='card__body';
  const kicker=document.createElement('div'); kicker.className='card__kicker';
  kicker.textContent=item.tag||(item.is_video?'Video':'News');

  const title=document.createElement('div'); title.className='card__title';
  title.textContent=(item.title||'').replace(/&[#0-9a-z]+;/gi,' ');

  const meta=document.createElement('div'); meta.className='card__meta';
  const src=document.createElement('span'); src.className='badge'; src.textContent=prettySource(item.source||'');
  const d=item.date?new Date(item.date):null; const when=document.createElement('span'); when.textContent=d?d.toLocaleDateString(undefined,{month:'short',day:'numeric'}):'';

  if(item.is_video && item.duration_seconds){
    const dur=document.createElement('span'); dur.className='badge'; dur.textContent=formatDuration(item.duration_seconds);
    meta.append(src,dur,when);
  } else {
    meta.append(src,when);
  }

  body.append(kicker,title,meta);

  if(item.is_video && isYouTube(item.url)){
    const cta=document.createElement('span'); cta.className='badge'; cta.textContent='Watch on YouTube'; body.appendChild(cta);
  }

  a.append(thumb,body);
  return a;
}

/* ---------- grids / carousel ---------- */
function renderGrid(items, sel, initial=12){
  const grid=qs(sel); if(!grid) return;
  grid.innerHTML='';
  let shown=0;

  if(!items.length){
    grid.innerHTML='<div class="empty">No items.</div>';
    return;
  }
  const slice=(n)=>{ items.slice(shown,shown+n).forEach((it,idx)=>{ const c=makeCard(it); if(sel==='#video-grid'&&shown+idx<2)c.classList.add('hero'); grid.appendChild(c); }); shown+=n; };
  slice(Math.min(initial,items.length));
  if(shown<items.length){
    const btn=document.createElement('button'); btn.className='load-more'; btn.textContent='Load more';
    btn.onclick=()=>{ slice(Math.min(12,items.length-shown)); if(shown>=items.length) btn.remove(); };
    grid.after(btn);
  }
}
function renderCarousel(items){
  const el=qs('#carousel'); if(!el) return;
  el.innerHTML='';
  const featured=items.filter(it => it.pinned || /BoilerBall|Purdue Athletics|GoldandBlack/i.test(prettySource(it.source||'')));
  if(!featured.length){ el.style.display='none'; return; }
  featured.slice(0,6).forEach(i=>el.appendChild(makeCard(i)));
  el.style.display='';
}

/* ---------- widgets ---------- */
function renderRankings(w){
  const el=qs('#rankings-body'); if(!el) return;
  el.innerHTML='';
  const rows=[['AP Rank',w?.ap_rank??'—'],['KenPom',w?.kenpom??'—'],['NET',w?.net??'—']];
  const ul=document.createElement('ul'); ul.className='list';
  rows.forEach(([k,v])=>{ const li=document.createElement('li'); li.innerHTML=`<span>${k}</span><strong>${v}</strong>`; ul.appendChild(li); });
  el.appendChild(ul);
}

function renderSchedule(sch){
  const el=qs('#schedule-body'); if(!el) return;
  el.innerHTML='';
  const games=sch?.games||[]; if(!games.length){ el.innerHTML='<div class="empty">No games scheduled.</div>'; return; }
  const now=new Date();
  const past=games.filter(g=>new Date(g.date)<=now).sort((a,b)=>new Date(b.date)-new Date(a.date)).slice(0,3);
  const up  =games.filter(g=>new Date(g.date)> now).sort((a,b)=>new Date(a.date)-new Date(b.date)).slice(0,3);
  let html='';
  if(past.length){ html+="<strong>Last 3 Results</strong><ul class='list'>"; past.forEach(g=>{ const d=new Date(g.date); const badge=(g.result&&g.score)?`${g.result} • ${g.score}`:(g.status==='final'?'Final':g.venue||''); html+=`<li><span>${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}</span><span>${badge}</span></li>`; }); html+='</ul>'; }
  if(up.length){ html+="<strong>Next 3 Games</strong><ul class='list'>"; up.forEach(g=>{ const d=new Date(g.date); let badge=g.venue||(g.home?'Home':'Away')||''; if(g.status==='live') badge='LIVE'; html+=`<li><span>${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}</span><span>${badge}</span></li>`; }); html+='</ul>'; }
  el.innerHTML=html || '<div class="empty">No games found.</div>';
}

function renderQuickLinks(w){
  const el=qs('#quicklinks-body'); if(!el) return;
  el.innerHTML='';
  const links=w?.quick_links||[];
  if(!links.length){ el.innerHTML='<div class="empty">Add quick links in static/widgets.json.</div>'; return; }
  const ul=document.createElement('ul'); ul.className='list';
  links.forEach(l=>{ const li=document.createElement('li'); li.innerHTML=`<a href="${l.url}" target="_blank" rel="noopener">${l.name}</a><span>${l.note||''}</span>`; ul.appendChild(li); });
  el.appendChild(ul);
}

function renderInsider(w){
  const el=qs('#insider-body'); if(!el) return;
  el.innerHTML='';
  const links=w?.insider||[];
  if(!links.length){ el.innerHTML='<div class="empty">Add insider links in static/widgets.json.</div>'; return; }
  const ul=document.createElement('ul'); ul.className='list';
  links.forEach(l=>{ const li=document.createElement('li'); li.innerHTML=`<a href="${l.url}" target="_blank" rel="noopener">${l.name}</a><span>${l.note||''}</span>`; ul.appendChild(li); });
  el.appendChild(ul);
}

/* ---------- counts / render pipeline ---------- */
function updateChipCounts(items){
  const news = items.filter(i=>!i.is_video).length;
  const vids = items.filter(i=> i.is_video).length;
  qsa('.tabs .chip').forEach(btn=>{
    if(btn.dataset.tab==='news')   btn.textContent=`News (${news})`;
    if(btn.dataset.tab==='videos') btn.textContent=`Videos (${vids})`;
  });
}

function renderAll(){
  let items=state.items;
  if(state.searchTerm){
    items = items.filter(i =>
      (i.title||'').toLowerCase().includes(state.searchTerm) ||
      (i.source||'').toLowerCase().includes(state.searchTerm)
    );
  }
  const news=items.filter(i=>!i.is_video), vids=items.filter(i=>i.is_video);
  renderCarousel(items);
  renderGrid(news,'#news-grid',12);
  renderGrid(vids,'#video-grid',8);
  updateChipCounts(items);
}

/* ---------- boot ---------- */
async function boot(){
  // skeletons so it never looks empty while fetching
  qs('#news-grid').innerHTML  = '<div class="skel card"></div><div class="skel card"></div>';
  qs('#video-grid').innerHTML = '<div class="skel card"></div><div class="skel card"></div>';

  try{
    const teamCfg=await safeJSON(paths.team).then(t=>t.teams?.[state.teamSlug]||Object.values(t.teams||{})[0]);
    document.title=`${teamCfg.name} — Team Hub`;
    qs('#site-title').textContent=teamCfg.name;
    if(teamCfg.logo) qs('#team-logo').src=teamCfg.logo;
    document.documentElement.style.setProperty('--accent',teamCfg.colors.accent);

    const [itemsJson,widgetsAll,scheduleAll]=await Promise.all([
      safeJSON(paths.items(state.teamSlug)),
      safeJSON(paths.widgets),
      safeJSON(paths.schedule)
    ]);

    const raw = (itemsJson.items||[]).map(i=>({...i,title:(i.title||'').replace(/<[^>]+>/g,'')}));
    state.items = raw;

    // Ticker + main grids
    renderTicker(raw);
    renderAll();

    // Widgets
    const widgets = widgetsAll[state.teamSlug] || widgetsAll.default || {};
    renderRankings(widgets);
    renderSchedule(scheduleAll[state.teamSlug] || scheduleAll);
    renderQuickLinks(widgets);
    renderInsider(widgets);

    // Footer health
    const foot=qs('.app-footer');
    if(foot && itemsJson.generated_at){
      const gen=new Date(itemsJson.generated_at);
      foot.textContent = `Updated ${gen.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} • ${itemsJson.total_sources||'?'} sources`;
    }
  }catch(e){
    console.error(e);
    qs('#news-grid').innerHTML='<div class="empty">Error loading data.</div>';
  }

  initTabs();
  initSearch();
  qs('#refresh')?.addEventListener('click',()=>location.reload());
}

document.addEventListener('DOMContentLoaded', boot);