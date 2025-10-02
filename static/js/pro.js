/* App JS v1.8 — Featured carousel, search, quick links widget, game-day state, health footer */

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

/* ---------- UI helpers ---------- */
function initTabs(){
  qsa('.tabs .chip').forEach(btn=>{
    btn.addEventListener('click',()=>{
      qsa('.tabs .chip').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const tab=btn.dataset.tab;
      qsa('.tab').forEach(sec=>sec.classList.remove('visible'));
      const active = qs('#'+tab);
      if (active) active.classList.add('visible');
    });
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

/* ---------- Card helpers ---------- */
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
  const a=document.createElement('