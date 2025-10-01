/* App JS — nav, ticker, cards, widgets */

const qs = (s, el=document) => el.querySelector(s);
const qsa = (s, el=document) => [...el.querySelectorAll(s)];

const state = { teamSlug: new URL(location.href).searchParams.get('team') || 'purdue-mbb' };

const paths = {
  team: 'static/team.json',
  items: (slug) => `static/teams/${slug}/items.json`,
  widgets: 'static/widgets.json',
  schedule: 'static/schedule.json'
};

function decodeEntities(str){ if(!str) return ''; const t=document.createElement('textarea'); t.innerHTML=str; return t.value; }
function html(str){ const d=document.createElement('div'); d.innerHTML=str.trim(); return d.firstChild; }
function safeJSON(url){ return fetch(url,{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})); }

function initTabs(){
  qsa('.tabs .chip').forEach(btn=>{
    btn.addEventListener('click',()=>{
      qsa('.tabs .chip').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const tab=btn.dataset.tab;
      qsa('.tab').forEach(sec=>sec.classList.remove('visible'));
      qs('#'+tab).classList.add('visible');
    });
  });
}

function renderTicker(items){
  const ticker=qs('#ticker'), track=qs('#ticker-track');
  const list=(items||[]).filter(i=>i.url&&i.title).slice(0,16).map(i=>`<a href="${i.url}" target="_blank">${decodeEntities(i.title)}</a>`);
  if(list.length<3){ticker.classList.add('hidden');return;}
  ticker.classList.remove('hidden'); track.innerHTML=[...list,...list].join(' • ');
  const dur=Math.max(22,Math.min(55,Math.round(track.scrollWidth/64)));
  track.style.animation=`marquee ${dur}s linear infinite`;
}

const FALLBACK_SVG=encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675"><rect fill="#101726" width="1200" height="675"/><text x="50%" y="52%" text-anchor="middle" fill="#415070" font-family="system-ui,Segoe UI,Roboto" font-size="42">Sports App Project</text></svg>`);

function makeCard(item){
  const a=document.createElement('a'); a.className='card'; a.href=item.url||'#'; a.target='_blank';
  const thumb=document.createElement('div'); thumb.className='card__thumb';
  const img=document.createElement('img'); img.loading='lazy'; img.src=item.image||item.thumbnail||`data:image/svg+xml,${FALLBACK_SVG}`;
  if(!item.image&&!item.thumbnail) thumb.classList.add('placeholder');
  img.alt=decodeEntities(item.title||''); thumb.appendChild(img);
  const body=document.createElement('div'); body.className='card__body';
  const kicker=document.createElement('div'); kicker.className='card__kicker'; kicker.textContent=item.tag||(item.is_video?'Video':'News');
  const title=document.createElement('div'); title.className='card__title'; title.textContent=decodeEntities(item.title||'');
  const meta=document.createElement('div'); meta.className='card__meta';
  const d=item.date?new Date(item.date):null; meta.textContent=[item.source||'',d?d.toLocaleDateString(undefined,{month:'short',day:'numeric'}):''].filter(Boolean).join(' • ');
  body.append(kicker,title,meta); a.append(thumb,body); return a;
}

function renderCarousel(items){const el=qs('#carousel');el.innerHTML='';items.slice(0,8).forEach(i=>el.appendChild(makeCard(i)));}

function renderGrid(items,sel){const grid=qs(sel);grid.innerHTML='';if(!items.length){grid.innerHTML='<div class="empty">No items yet.</div>';return;}items.slice(0,24).forEach(i=>grid.appendChild(makeCard(i)));}

function renderRankings(w){const el=qs('#rankings-body');el.innerHTML='';const rows=[['AP Rank',w?.ap_rank??'—'],['KenPom',w?.kenpom??'—'],['NET',w?.net??'—']];const ul=document.createElement('ul');ul.className='list';rows.forEach(([k,v])=>{const li=document.createElement('li');li.innerHTML=`<span>${k}</span><strong>${v}</strong>`;ul.appendChild(li);});el.appendChild(ul);}
function renderSchedule(sch){const el=qs('#schedule-body');el.innerHTML='';const games=sch?.games||[];if(!games.length){el.innerHTML='<div class="empty">No upcoming games.</div>';return;}const ul=document.createElement('ul');ul.className='list';games.slice(0,6).forEach(g=>{const d=new Date(g.date);const li=document.createElement('li');li.innerHTML=`<span>${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}</span><span>${g.venue||''}</span>`;ul.appendChild(li);});el.appendChild(ul);}
function renderNIL(w){const el=qs('#nil-body');el.innerHTML='';const list=w?.nil||[];if(!list.length){el.innerHTML='<div class="empty">NIL data not available.</div>';return;}const ul=document.createElement('ul');ul.className='list';list.slice(0,5).forEach(p=>{const li=document.createElement('li');li.innerHTML=`<span>${p.name}</span><span>${p.value}</span>`;ul.appendChild(li);});el.appendChild(ul);}
function renderInsider(w){const el=qs('#insider-body');el.innerHTML='';const links=w?.insider||[];if(!links.length){el.innerHTML='<div class="empty">Add insider links in static/widgets.json.</div>';return;}const ul=document.createElement('ul');ul.className='list';links.forEach(l=>{const li=document.createElement('li');li.innerHTML=`<a href="${l.url}" target="_blank">${l.name}</a><span>${l.note||''}</span>`;ul.appendChild(li);});el.appendChild(ul);}

async function boot(){
  initTabs();
  qs('#carousel').innerHTML='<div class="skel card"></div>';
  qs('#news-grid').innerHTML='<div class="skel card"></div><div class="skel card"></div>';
  qs('#video-grid').innerHTML='<div class="skel card"></div><div class="skel card"></div>';
  try{
    const teamCfg=await safeJSON(paths.team).then(t=>t.teams?.[state.teamSlug]||Object.values(t.teams||{})[0]);
    document.title=`${teamCfg.name} — Team Hub`;qs('#site-title').textContent=teamCfg.name;if(teamCfg.logo)qs('#team-logo').src=teamCfg.logo;
    document.documentElement.style.setProperty('--accent',teamCfg.colors.accent);document.documentElement.style.setProperty('--bg',teamCfg.colors.bg);document.documentElement.style.setProperty('--card',teamCfg.colors.card);
    const [itemsJson,widgetsAll,scheduleAll]=await Promise.all([safeJSON(paths.items(state.teamSlug)),safeJSON(paths.widgets),safeJSON(paths.schedule)]);
    let items=(itemsJson.items||[]).map(i=>({...i,title:decodeEntities(i.title)}));
    if(!items.length){items=[{title:'Welcome to your Team Hub — connect feeds.',url:'#',image:'',source:'Sports App Project',date:new Date().toISOString(),tag:'News'}];}
    const widgets=widgetsAll[state.teamSlug]||widgetsAll.default||{};const schedule=scheduleAll[state.teamSlug]||scheduleAll;
    const news=items.filter(i=>!i.is_video), vids=items.filter(i=>i.is_video);
    renderTicker(items);renderCarousel(news.length?news:items);renderGrid(news.length?news:items,'#news-grid');renderGrid(vids,'#video-grid');
    renderRankings(widgets);renderSchedule(schedule);renderNIL(widgets);renderInsider(widgets);
  }catch(e){console.error(e);qs('#news-grid').innerHTML='<div class="empty">Error loading data.</div>';}
  qs('#refresh').addEventListener('click',()=>location.reload());
}
document.addEventListener('DOMContentLoaded',boot);
