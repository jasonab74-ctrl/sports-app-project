import fs from 'fs';

const SITE_URL = 'https://jasonab74-ctrl.github.io/sports-app-project/';
const SITE_NAME = 'Purdue MBB Hub';
const SITE_DESC = 'Fast Purdue Men’s Basketball hub: top headlines, videos, rankings, schedule, insiders.';
const ASSET_VER = '20251005c';

// data files
const ITEMS_PATH     = 'static/teams/purdue-mbb/items.json';
const WIDGETS_PATH   = 'static/widgets.json';
const SCHED_PATH     = 'static/schedule.json';
const INS_PATH       = 'static/insiders.json';
const ROSTER_PATH    = 'static/teams/purdue-mbb/roster.json';
const OVERRIDES_PATH = 'static/image-overrides.json';

// utils
const esc = (s='') => String(s).replace(/[&<>"']/g,m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#039;' }[m]));
const initialsFrom = (str='') => { const p=(str||'').trim().split(/\s+/); return (p[0]?.[0]||'')+(p[1]?.[0]||'') || '•'; };
const safeJSON = (p,def)=>{ try{ return JSON.parse(fs.readFileSync(p,'utf8')); }catch{ return def; } };
const fileExists = p => { try{ return fs.existsSync(p); }catch{ return false; } };
const safeDate = v => { const d=v?new Date(v):null; return d&&!isNaN(+d)?d:null; };

// read data
const ITEMS    = (safeJSON(ITEMS_PATH,{items:[]}).items)||[];
const WIDGETS  = safeJSON(WIDGETS_PATH,{});
const SCHEDULE = safeJSON(SCHED_PATH,[]);
const INSIDERS = safeJSON(INS_PATH,[]);
const ROSTER   = fileExists(ROSTER_PATH)?safeJSON(ROSTER_PATH,[]):[];
const OVERRIDES= safeJSON(OVERRIDES_PATH,{});

// artwork: SSR uses local posters or initials only (no remote images)
function posterForLink(link=''){
  try{
    const u = new URL(link);
    const h = u.hostname.toLowerCase();
    if (OVERRIDES[h]) return OVERRIDES[h];
    const bare = h.replace(/^www\./,'');
    if (OVERRIDES[bare]) return OVERRIDES[bare];
  }catch{}
  return null;
}
function posterTag({link,label='',aspect='4x3',eager=false}){
  const wh = aspect==='16x9' ? {w:1280,h:720} : {w:1200,h:900};
  const poster = posterForLink(link);
  if (poster) {
    return `<img class="${aspect==='16x9'?'hero-img':'card-img'}"
             src="${esc(poster)}" alt="${esc(label)}" width="${wh.w}" height="${wh.h}"
             loading="${eager?'eager':'lazy'}" decoding="async">`;
  }
  return `<div class="fallback-${aspect}"><div class="fallback-badge">${esc(initialsFrom(label))}</div></div>`;
}

// partition
const looksVideo = u=>{ try{const h=new URL(u).hostname;return /youtube\.com$|youtu\.be$/.test(h);}catch{return false;} };
const videoItems = ITEMS.filter(i => (i.type||'').toLowerCase()==='video' || looksVideo(i.link));
const newsItems  = ITEMS.filter(i => !((i.type||'').toLowerCase()==='video' || looksVideo(i.link)));

// hero + grid (guard if empty)
const lead = newsItems[0] || null;
const heroHTML = lead ? `
<div id="hero" class="hero">
  <a href="${esc(lead.link)}" target="_blank" rel="noopener" class="hero-img-wrap">
    ${posterTag({link:lead.link,label:(lead.source?`${lead.source}: ${lead.title}`:lead.title||''),aspect:'16x9',eager:true})}
  </a>
  <div class="hero-meta">
    <div class="pills">
      ${lead?.tier?`<span class="pill">${esc(lead.tier)}</span>`:''}
      ${lead?.source?`<span class="pill">${esc(lead.source)}</span>`:''}
    </div>
    <h3 class="hero-title"><a href="${esc(lead.link)}" target="_blank" rel="noopener">${esc(lead.title||'')}</a></h3>
  </div>
</div>` : '';

const newsGrid = (newsItems.slice(lead?1:0, 12)).map(i=>{
  const label = (i.source?`${i.source}: ${i.title}`:i.title||'');
  const tier  = (i.tier||'').toLowerCase();
  const safeT = ['official','insiders','national'].includes(tier)?tier:'all';
  return `<article class="card" data-tier="${safeT}">
    <a class="card-img-wrap" href="${esc(i.link)}" target="_blank" rel="noopener">
      ${posterTag({link:i.link,label,aspect:'4x3'})}
    </a>
    <div class="card-body">
      <a class="card-title" href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title||'')}</a>
    </div>
  </article>`;
}).join('');

const videoGrid = videoItems.slice(0,9).map(v=>{
  const label = (v.source?`${v.source}: ${v.title}`:v.title||'');
  return `<article class="card video-card">
    <a class="card-img-wrap" href="${esc(v.link)}" target="_blank" rel="noopener">
      ${posterTag({link:v.link,label,aspect:'16x9'})}
    </a>
    <div class="card-body"><a class="card-title" href="${esc(v.link)}" target="_blank" rel="noopener">${esc(v.title||'')}</a></div>
  </article>`;
}).join('');

// empty-states
const newsSectionBody = (newsItems.length===0)
  ? `<div class="empty">No headlines yet. Checking your sources hourly.</div>`
  : `${heroHTML}<div class="card-grid" id="news-grid">${newsGrid}</div>`;

// ticker
const ticker = ITEMS.slice(0,12).map(i=>`<span style="margin:0 1.25rem">${esc(i.source||'')} — ${esc(i.title||'')}</span>`).join('');

// schedule
const parseGame=g=>{const d=safeDate(g.utc||g.date);return d?{...g,_dt:d}:null;};
const games=(SCHEDULE||[]).map(parseGame).filter(Boolean);
const now=Date.now();
const fmtDay=d=>d.toLocaleDateString([],{year:'numeric',month:'2-digit',day:'2-digit'});
const fmtTime=d=>d.toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});
const upcoming=games.filter(g=>+g._dt>=now).sort((a,b)=>+a._dt-+b._dt).slice(0,6);
const recent  =games.filter(g=>+g._dt< now).sort((a,b)=>+b._dt-+a._dt).slice(0,5);

const scheduleUpcomingHTML = upcoming.map(g=>`
  <a class="game" href="${esc(g.espn_url||g.tickets_url||'#')}" target="_blank" rel="noopener">
    <div class="g-top"><span>${esc(fmtDay(g._dt))}</span><span>${esc(fmtTime(g._dt))} <small>local</small></span></div>
    <div class="g-title"><span class="logo-pill">${esc(initialsFrom(g.opp||''))}</span> ${esc(g.opp||'Opponent')} <span class="pill">${esc(g.site||'TBD')}</span></div>
  </a>`).join('');

const scheduleRecentHTML = recent.map(g=>{
  const outcome=(g.outcome||'').toUpperCase(); const wl= outcome==='W'?'win':(outcome==='L'?'loss':'');
  const recap=g.recap_url?`<a class="res-link" href="${esc(g.recap_url)}" target="_blank" rel="noopener">Recap</a>`:'';
  const box  =g.box_url?`<a class="res-link" href="${esc(g.box_url)}" target="_blank" rel="noopener">Box</a>`:'';
  return `<div class="result">
    <div class="res-line"><span class="res-date">${esc(fmtDay(g._dt))}</span>${outcome?`<span class="wl-pill ${wl}">${outcome}</span>`:''}<span class="res-opp">${esc(g.opp||'Opponent')}</span>${g.final_score?`<span class="res-score">${esc(g.final_score)}</span>`:''}</div>
    <div class="res-meta">${recap}${box}</div>
  </div>`;
}).join('');

// roster (safe)
function rosterImg(p){
  const src=(p.headshot||'').trim();
  const label=`${p.name} (${p.pos})`;
  if (src){
    return `<img class="player-img" src="${esc(src)}" alt="${esc(label)}" width="600" height="800" loading="lazy" decoding="async">`;
  }
  return `<svg class="player-img" aria-label="${esc(label)}" role="img" viewBox="0 0 600 800" xmlns="http://www.w3.org/2000/svg">
    <rect width="600" height="800" fill="#111"/><circle cx="300" cy="240" r="110" fill="#1b1b1f"/><rect x="150" y="360" width="300" height="260" rx="30" fill="#1b1b1f"/></svg>`;
}
const rosterCards=(Array.isArray(ROSTER)?ROSTER:[]).map(p=>`
  <article class="player" tabindex="0" aria-label="${esc(p.name)}">
    ${rosterImg(p)}
    <div class="player-body">
      <div class="player-top"><div class="player-name">${esc(p.name)}</div><div class="player-num">#${esc(p.num)}</div></div>
      <div class="player-meta"><span>${esc(p.pos)}</span><span>${esc(p.ht)} • ${esc(p.wt)}</span><span>${esc(p.class)}</span></div>
      <div class="player-meta">${esc(p.hometown||'')}</div>
      ${p.bio?`<div class="player-bio">${esc(p.bio)}</div>`:''}
    </div>
  </article>`).join('');

// head
const HEAD = `
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${esc(SITE_NAME)}</title>
<meta name="description" content="${esc(SITE_DESC)}"/>
<link rel="canonical" href="${SITE_URL}"/>
<link rel="icon" href="static/logo.png" type="image/png"/><link rel="apple-touch-icon" href="static/logo.png"/>
<link rel="stylesheet" href="static/css/pro.css?v=${ASSET_VER}"/>
`;

// chips
const CHIPS = `
<div class="chips" data-filter-ready>
  <button class="chip is-active" data-filter="all" aria-pressed="true">All</button>
  <button class="chip" data-filter="official" aria-pressed="false">Official</button>
  <button class="chip" data-filter="insiders" aria-pressed="false">Insiders</button>
  <button class="chip" data-filter="national" aria-pressed="false">National</button>
</div>`;

// page
const HTML = `<!doctype html><html lang="en"><head>${HEAD}</head><body>
<header class="topbar"><a class="brand" href="./"><div class="brand-line1">Team Hub</div><div class="brand-line2">Boilermakers</div></a></header>
<section class="ticker" aria-live="polite"><div class="ticker-track">${
  ITEMS.slice(0,12).map(i=>`<span style="margin:0 1.25rem">${esc(i.source||'')} — ${esc(i.title||'')}</span>`).join('')
}</div></section>
<main class="container">
  <section id="news" class="panel">
    <div class="panel-hd"><h2>Top Headlines</h2>${CHIPS}</div>
    ${newsSectionBody}
  </section>
  <aside class="rail">
    <section id="rankings" class="panel"><div class="panel-hd"><h3>Rankings</h3></div>
      <div class="rankings">
        <div class="rank-line"><span>AP Top 25:</span> <b>${WIDGETS.ap_rank?`#${esc(WIDGETS.ap_rank)}`:'—'}</b> ${WIDGETS.ap_url?`<a href="${esc(WIDGETS.ap_url)}" target="_blank" rel="noopener">View</a>`:''}</div>
        <div class="rank-line"><span>KenPom:</span> <b>${WIDGETS.kenpom_rank?`#${esc(WIDGETS.kenpom_rank)}`:'—'}</b> ${WIDGETS.kenpom_url?`<a href="${esc(WIDGETS.kenpom_url)}" target="_blank" rel="noopener">View</a>`:''}</div>
      </div>
    </section>
    <section id="schedule" class="panel"><div class="panel-hd"><h3>Upcoming Schedule</h3></div>
      <div class="schedule-list">${scheduleUpcomingHTML || '<div class="muted">No upcoming games</div>'}</div>
      <div class="panel-hd" style="margin-top:.75rem"><h3>Recent Results</h3></div>
      <div class="results-list">${scheduleRecentHTML || '<div class="muted">No recent games</div>'}</div>
    </section>
    <section id="insiders" class="panel"><div class="panel-hd"><h3>Insider / Beat Links</h3></div>
      <div class="links-grid">${
        (INSIDERS||[]).map(o=>`
          <a class="link-card" href="${esc(o.latest_url||o.url||'#')}" target="_blank" rel="noopener">
            <div class="link-logo">📰</div>
            <div class="link-body"><div class="link-title">${esc(o.name||'')}</div>${o.latest_headline?`<div class="link-sub">${esc(o.latest_headline)}</div>`:''}</div>
            <div class="link-meta">${esc(o.type||'')}${o.pay?' <span class="badge-pay">$</span>':''}</div>
          </a>`).join('')
      }</div>
    </section>
  </aside>
  <section id="roster" class="panel"><div class="panel-hd"><h2>Roster</h2></div><div class="roster-grid">${rosterCards}</div></section>
  <section id="videos" class="panel"><div class="panel-hd"><h2>Latest Videos</h2></div><div class="video-grid">${videoGrid}</div></section>
</main>
<footer class="footer"><div>Updated ${new Date().toLocaleString()}</div></footer>
</body></html>`;

fs.writeFileSync('index.html', HTML);
console.log('✅ SSR built: posters/initials only, empty states guarded');