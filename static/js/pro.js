/* App JS v1.7 — News/Video hub with search, featured carousel, game-day state, health footer */

const qs = (s, el=document) => el.querySelector(s);
const qsa = (s, el=document) => [...el.querySelectorAll(s)];

const state = {
  teamSlug: new URL(location.href).searchParams.get('team') || 'purdue-mbb',
  items: [],
  searchTerm: ''
};

const paths = {
  team: 'static/team.json',
  items: (slug) => `static/teams/${slug}/items.json`,
  widgets: 'static/widgets.json',
  schedule: 'static/schedule.json'
};

function decodeEntities(str){ if(!str) return ''; const t=document.createElement('textarea'); t.innerHTML=str; return t.value; }
function safeJSON(url){ return fetch(url,{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})); }

/* Source label map */
function prettySource(src){
  if(!src) return '';
  const s = (src||'').toLowerCase();
  if(s.includes('boilerball')) return 'BoilerBall';
  if(s.includes('purduesports')) return 'Purdue Athletics';
  if(s.includes('hammerandrails')) return 'Hammer & Rails';
  if(s.includes('goldandblack')) return 'GoldandBlack';
  if(s.includes('on3.com')) return 'On3';
  if(s.includes('si.com')) return 'Sports Illustrated';
  if(s.includes('youtube')) return 'YouTube';
  return src.replace(/^www\./,'');
}

/* Duration formatting */
function formatDuration(sec){
  sec = Number(sec||0);
  if(!sec) return '';
  const h = Math.floor(sec/3600);
  const m = Math.floor((sec%3600)/60);
  const s = sec%60;
  if(h) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${m}:${String(s).padStart(2,'0')}`;
}
function isYouTube(u){ u=(u||'').toLowerCase(); return u.includes('youtube.com')||u.includes('youtu.be'); }

const FALLBACK_NEWS = 'static/img/fallback-news.svg';

/* === Cards === */
function makeCard(item){
  const a=document.createElement('a'); a.className='card'; a.href=item.url||'#'; a.target='_blank' ; a.rel='noopener';
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
  const srcBadge=document.createElement('span'); srcBadge.className='badge'; srcBadge.textContent=prettySource(item.source||'');
  const d=item.date?new Date(item.date):null; const when=document.createElement('span'); when.textContent=d?d.toLocaleDateString(undefined,{month:'short',day:'numeric'}):'';

  // Duration badge
  if(item.is_video && item.duration_seconds){
    const dur=document.createElement('span'); dur.className='badge'; dur.textContent=formatDuration(item.duration_seconds);
    meta.append(srcBadge,dur,when);
  } else { meta.append(srcBadge,when); }

  body.append(kicker,title,meta);

  // CTA
  if(item.is_video && isYouTube(item.url)){
    const cta=document.createElement('span'); cta.className='badge'; cta.textContent='Watch on YouTube'; body.appendChild(cta);
  }

  a.append(thumb,body); return a;
}

/* === Grid + Carousel === */
function renderGrid(items,sel,initial=12){
  const grid=qs(sel); grid.innerHTML=''; let shown=0;
  if(!items.length){grid.innerHTML='<div class="empty">No items.</div>';return;}
  const renderSlice=(n)=>{items.slice(shown,shown+n).forEach((it,idx)=>{const c=makeCard(it);if(sel==='#video-grid'&&shown+idx<2)c.classList.add('hero');grid.appendChild(c);});shown+=n;};
  renderSlice(Math.min(initial,items.length));
  if(shown<items.length){const btn=document.createElement('button');btn.className='load-more';btn.textContent='Load more';btn.onclick=()=>{renderSlice(Math.min(12,items.length-shown));if(shown>=items.length)btn.remove();};grid.after(btn);}
}

function renderCarousel(items){
  const el=qs('#carousel');el.innerHTML='';
  const featured=items.filter(it=>it.pinned||prettySource(it.source).match(/BoilerBall|Purdue Athletics|GoldandBlack/));
  if(!featured.length){el.style.display='none';return;}
  featured.slice(0,6).forEach(i=>el.appendChild(makeCard(i)));
  el.style.display='';
}

/* === Widgets === */
function renderRankings(w){const el=qs('#rankings-body');el.innerHTML='';const rows=[['AP Rank',w?.ap_rank??'—'],['KenPom',w?.kenpom??'—'],['NET',w?.net??'—']];const ul=document.createElement('ul');ul.className='list';rows.forEach(([k,v])=>{const li=document.createElement('li');li.innerHTML=`<span>${k}</span><strong>${v}</strong>`;ul.appendChild(li);});el.appendChild(ul);}

function renderSchedule(sch){
  const el=qs('#schedule-body');el.innerHTML='';
  const games=sch?.games||[]; if(!games.length){el.innerHTML='<div class="empty">No games scheduled.</div>';return;}
  const now=new Date();const past=games.filter(g=>new Date(g.date)<=now).sort((a,b)=>new Date(b.date)-new Date(a.date)).slice(0,3);const upcoming=games.filter(g=>new Date(g.date)>now).sort((a,b)=>new Date(a.date)-new Date(b.date)).slice(0,3);
  let html='';if(past.length){html+="<strong>Last 3 Results</strong><ul class='list'>";past.forEach(g=>{const d=new Date(g.date);const badge=(g.result&&g.score)?`${g.result} • ${g.score}`:g.venue||"";html+=`<li><span>${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}</span><span>${badge}</span></li>`;});html+='</ul>';}
  if(upcoming.length){html+="<strong>Next 3 Games</strong><ul class='list'>";upcoming.forEach(g=>{const d=new Date(g.date);let badge=g.venue||(g.home?'Home':'Away')||'';if(g.status==='live')badge='LIVE';if(g.status==='final')badge='Final';html+=`<li><span>${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}</span><span>${badge}</span></li>`;});html+='</ul>';}
  el.innerHTML=html;
}

function renderNIL(w){const el=qs('#nil-body');el.innerHTML='';const list=w?.nil||[];if(!list.length){el.innerHTML='<div class="empty">NIL data not available.</div>';return;}const ul=document.createElement('ul');ul.className='list';list.slice(0,5).forEach(p=>{const li=document.createElement('li');li.innerHTML=`<span>${p.name}</span><span>${p.value}</span>`;ul.appendChild(li);});el.appendChild(ul);}
function renderInsider(w){const el=qs('#insider-body');el.innerHTML='';const links=w?.insider||[];if(!links.length){el.innerHTML='<div class="empty">Add insider links in static/widgets.json.</div>';return;}const ul=document.createElement('ul');ul.className='list';links.forEach(l=>{const li=document.createElement('li');li.innerHTML=`<a href="${l.url}" target="_blank" rel="noopener">${l.name}</a><span>${l.note||''}</span>`;ul.appendChild(li);});el.appendChild(ul);}

/* === Search === */
function initSearch(){
  const box=document.createElement('input');box.type='search';box.placeholder='Search news & videos…';box.className='search-box';
  qs('.tabs').before(box);
  box.addEventListener('input',()=>{state.searchTerm=box.value.toLowerCase();renderAll();});
}

/* === Render pipeline === */
function renderAll(){
  let items=state.items; if(state.searchTerm){items=items.filter(i=>(i.title||'').toLowerCase().includes(state.searchTerm)||(i.source||'').toLowerCase().includes(state.searchTerm));}
  const news=items.filter(i=>!i.is_video), vids=items.filter(i=>i.is_video);
  renderCarousel(items); renderGrid(news,'#news-grid',12); renderGrid(vids,'#video-grid',8);
  updateChipCounts(items);
}
function updateChipCounts(items){const news=items.filter(i=>!i.is_video).length;const vids=items.filter(i=>i.is_video).length;qsa('.tabs .chip').forEach(btn=>{const key=btn.dataset.tab;if(key==='news')btn.textContent=`News (${news})`;if(key==='videos')btn.textContent=`Videos (${vids})`;});}

/* === Boot === */
async function boot(){
  try{
    const teamCfg=await safeJSON(paths.team).then(t=>t.teams?.[state.teamSlug]||Object.values(t.teams||{})[0]);
    document.title=`${teamCfg.name} — Team Hub`;qs('#site-title').textContent=teamCfg.name;if(teamCfg.logo)qs('#team-logo').src=teamCfg.logo;
    document.documentElement.style.setProperty('--accent',teamCfg.colors.accent);

    const [itemsJson,widgetsAll,scheduleAll]=await Promise.all([safeJSON(paths.items(state.teamSlug)),safeJSON(paths.widgets),safeJSON(paths.schedule)]);
    state.items=(itemsJson.items||[]).map(i=>({...i,title:(i.title||'').replace(/<[^>]+>/g,'')}));

    renderAll(); renderRankings(widgetsAll[state.teamSlug]||widgetsAll.default||{}); renderSchedule(scheduleAll[state.teamSlug]||scheduleAll); renderNIL(widgetsAll[state.teamSlug]||{}); renderInsider(widgetsAll[state.teamSlug]||{});

    // Footer health line
    const foot=qs('.app-footer');if(foot&&itemsJson.generated_at){const gen=new Date(itemsJson.generated_at);foot.innerHTML=`Updated ${gen.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} • ${itemsJson.total_sources||'?'} sources`; }
  }catch(e){console.error(e);}
  initTabs();initSearch();
}
document.addEventListener('DOMContentLoaded',boot);