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
function safeJSON(url){ return fetch(url,{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})); }

/* helpers */
const none = v => v == null || v === '' || v === '—';
const show = (el, ok) => (el.closest('.widget').style.display = ok ? '' : 'none');

function initTabs(){
  qsa('.tabs .chip').forEach(btn=>{
    btn.addEventListener('click',()=>{
      qsa('.tabs .chip').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const tab=btn.dataset.tab;
      qsa('.tab').forEach(sec=>sec.classList.remove('visible'));
      const active = qs('#'+tab);
      active.classList.add('visible');
      active.setAttribute('aria-live','polite');
    });
  });
}

/* Ticker */
function renderTicker(items){
  const ticker=qs('#ticker'), track=qs('#ticker-track');
  const list=(items||[]).filter(i=>i.url&&i.title).slice(0,16).map(i=>`<a href="${i.url}" target="_blank" rel="noopener">${decodeEntities(i.title)}</a>`);
  if(list.length<3){ticker.classList.add('hidden');return;}
  ticker.classList.remove('hidden'); track.innerHTML=[...list,...list].join(' • ');
  const dur=Math.max(22,Math.min(55,Math.round(track.scrollWidth/64)));
  track.style.animation=`marquee ${dur}s linear infinite`;
}

const FALLBACK_SVG=encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675"><rect fill="#101726" width="1200" height="675"/><text x="50%" y="52%" text-anchor="middle" fill="#415070" font-family="system-ui,Segoe UI,Roboto" font-size="42">Sports App Project</text></svg>`);

function makeCard(item){
  const a=document.createElement('a'); a.className='card'; a.href=item.url||'#'; a.target='_blank' ; a.rel='noopener';
  const thumb=document.createElement('div'); thumb.className='card__thumb';
  const img=document.createElement('img'); img.loading='lazy'; img.decoding='async';
  img.src=item.image||item.thumbnail||`data:image/svg+xml,${FALLBACK_SVG}`;
  img.alt=(item.title||'').replace(/<[^>]+>/g,'');
  img.onerror=()=>{ img.src=`data:image/svg+xml,${FALLBACK_SVG}`; thumb.classList.add('placeholder'); };
  if(!(item.image||item.thumbnail)) thumb.classList.add('placeholder');
  thumb.appendChild(img);

  const body=document.createElement('div'); body.className='card__body';
  const kicker=document.createElement('div'); kicker.className='card__kicker'; kicker.textContent=item.tag||(item.is_video?'Video':'News');
  const title=document.createElement('div'); title.className='card__title'; title.textContent=(item.title||'').replace(/&[#0-9a-z]+;/gi,' ');
  const meta=document.createElement('div'); meta.className='card__meta';
  const d=item.date?new Date(item.date):null; meta.textContent=[item.source||'',d?d.toLocaleDateString(undefined,{month:'short',day:'numeric'}):''].filter(Boolean).join(' • ');
  body.append(kicker,title,meta); a.append(thumb,body); return a;
}

/* Grid rendering with Load more */
function renderGridWithMore(items, sel, initialCount=12){
  const grid=qs(sel);
  grid.innerHTML='';
  let shown = 0;
  const renderSlice = (n) => {
    items.slice(shown, shown+n).forEach((it, idx) => {
      const card = makeCard(it);
      // Video hero: mark first two videos in video grid
      if (sel === '#video-grid' && shown+idx < 2) card.classList.add('hero');
      grid.appendChild(card);
    });
    shown += n;
  };

  // mark video grid
  if (sel === '#video-grid') grid.classList.add('video');

  // initial render
  if (!items.length){ grid.innerHTML='<div class="empty">No items yet.</div>'; return; }
  renderSlice(Math.min(initialCount, items.length));

  // Load more button
  if (shown < items.length){
    const btn = document.createElement('button');
    btn.className = 'load-more';
    btn.textContent = 'Load more';
    btn.addEventListener('click', ()=>{
      renderSlice(Math.min(12, items.length - shown));
      if (shown >= items.length) btn.remove();
    });
    grid.after(btn);
  }
}

function renderRankings(w){
  const el=qs('#rankings-body');el.innerHTML='';
  const rows=[['AP Rank',w?.ap_rank??'—'],['KenPom',w?.kenpom??'—'],['NET',w?.net??'—']];
  const ul=document.createElement('ul');ul.className='list';
  rows.forEach(([k,v])=>{const li=document.createElement('li');li.innerHTML=`<span>${k}</span><strong>${v}</strong>`;ul.appendChild(li);});
  el.appendChild(ul);
  show(el, !(none(w?.ap_rank)&&none(w?.kenpom)&&none(w?.net)));
}

/* Schedule: Last 3 Results + Next 3 Games */
function renderSchedule(sch){
  const el=qs('#schedule-body');el.innerHTML='';
  const games=sch?.games||[];
  if(!games.length){el.innerHTML='<div class="empty">No games scheduled.</div>'; show(el,false); return;}

  const now = new Date();
  const past = games.filter(g => new Date(g.date) <= now).sort((a,b) => new Date(b.date)-new Date(a.date)).slice(0,3);
  const upcoming = games.filter(g => new Date(g.date) > now).sort((a,b) => new Date(a.date)-new Date(b.date)).slice(0,3);

  let html = "";

  if(past.length){
    html += "<strong>Last 3 Results</strong><ul class='list'>";
    past.forEach(g=>{
      const d=new Date(g.date);
      const left = `${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}`;
      const badge = (g.result && g.score) ? `${g.result} • ${g.score}` : (g.venue||"");
      html += `<li><span>${left}</span><span>${badge}</span></li>`;
    });
    html += "</ul>";
  }

  if(upcoming.length){
    html += "<strong>Next 3 Games</strong><ul class='list'>";
    upcoming.forEach(g=>{
      const d=new Date(g.date);
      const left = `${d.toLocaleDateString(undefined,{month:'short',day:'numeric'})} • ${g.opponent}`;
      const badge = g.venue|| (g.home ? "Home" : "Away") || "";
      html += `<li><span>${left}</span><span>${badge}</span></li>`;
    });
    html += "</ul>";
  }

  el.innerHTML = html || '<div class="empty">No games found.</div>';
  show(el,true);
}

function renderNIL(w){
  const el=qs('#nil-body');el.innerHTML='';
  const list=w?.nil||[];
  if(!list.length){el.innerHTML='<div class="empty">NIL data not available.</div>'; show(el,false); return;}
  const ul=document.createElement('ul');ul.className='list';
  list.slice(0,5).forEach(p=>{const li=document.createElement('li');li.innerHTML=`<span>${p.name}</span><span>${p.value}</span>`;ul.appendChild(li);});
  el.appendChild(ul);
  show(el, true);
}

function renderInsider(w){
  const el=qs('#insider-body');el.innerHTML='';
  const links=w?.insider||[];
  if(!links.length){el.innerHTML='<div class="empty">Add insider links in static/widgets.json.</div>'; show(el,false); return;}
  const ul=document.createElement('ul');ul.className='list';
  links.forEach(l=>{const li=document.createElement('li');li.innerHTML=`<a href="${l.url}" target="_blank" rel="noopener">${l.name}</a><span>${l.note||''}</span>`;ul.appendChild(li);});
  el.appendChild(ul);
  show(el, true);
}

/* Chip counts for News / Videos */
function updateChipCounts(items){
  const news = items.filter(i=>!i.is_video).length;
  const vids = items.filter(i=> i.is_video).length;
  const map = { news, videos: vids };
  qsa('.tabs .chip').forEach(btn=>{
    const key = btn.dataset.tab;
    if(map[key] != null){
      const base = btn.textContent.replace(/\s+\(\d+\)$/, '');
      btn.textContent = `${base} (${map[key]})`;
    }
  });
}

async function boot(){
  initTabs();

  // skeletons
  qs('#news-grid').innerHTML='<div class="skel card"></div><div class="skel card"></div>';
  qs('#video-grid').innerHTML='<div class="skel card"></div><div class="skel card"></div>';

  try{
    const teamCfg=await safeJSON(paths.team).then(t=>t.teams?.[state.teamSlug]||Object.values(t.teams||{})[0]);
    document.title=`${teamCfg.name} — Team Hub`;qs('#site-title').textContent=teamCfg.name;if(teamCfg.logo)qs('#team-logo').src=teamCfg.logo;
    document.documentElement.style.setProperty('--accent',teamCfg.colors.accent);
    document.documentElement.style.setProperty('--bg',teamCfg.colors.bg);
    document.documentElement.style.setProperty('--card',teamCfg.colors.card);

    const [itemsJson,widgetsAll,scheduleAll]=await Promise.all([
      safeJSON(paths.items(state.teamSlug)),
      safeJSON(paths.widgets),
      safeJSON(paths.schedule)
    ]);

    const raw = (itemsJson.items||[]).map(i=>({...i,title:(i.title||'').replace(/<[^>]+>/g,'')}));
    const news=raw.filter(i=>!i.is_video);
    const vids=raw.filter(i=> i.is_video);

    // Ticker uses latest across all types
    renderTicker(raw);

    // News grid + Videos grid with load more
    renderGridWithMore(news.length?news:raw, '#news-grid', 12);
    renderGridWithMore(vids, '#video-grid', 8);

    // Widgets
    const widgets=widgetsAll[state.teamSlug]||widgetsAll.default||{};
    const schedule=scheduleAll[state.teamSlug]||scheduleAll;
    renderRankings(widgets);renderSchedule(schedule);renderNIL(widgets);renderInsider(widgets);

    // Chip counts
    updateChipCounts(raw);

  }catch(e){
    console.error(e);
    qs('#news-grid').innerHTML='<div class="empty">Error loading data.</div>';
  }

  qs('#refresh').addEventListener('click',()=>location.reload());
}
document.addEventListener('DOMContentLoaded',boot);