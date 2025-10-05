import fs from 'fs';
import path from 'path';

const SITE_URL = 'https://jasonab74-ctrl.github.io/sports-app-project/';
const SITE_NAME = 'Purdue MBB Hub';
const SITE_DESC = 'Fast Purdue Men’s Basketball hub: top headlines, videos, rankings, schedule, insider links.';
const ASSET_VER = '20251005a'; // cache-bust CSS/JS

// Data files
const ITEMS_PATH     = 'static/teams/purdue-mbb/items.json';
const WIDGETS_PATH   = 'static/widgets.json';
const SCHED_PATH     = 'static/schedule.json';
const INS_PATH       = 'static/insiders.json';
const ROSTER_PATH    = 'static/teams/purdue-mbb/roster.json';
const OVERRIDES_PATH = 'static/image-overrides.json';

// ---------- utils ----------
const esc = (s='') => String(s).replace(/[&<>"']/g,m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#039;' }[m]));
const initialsFrom = (str='') => {
  const p = (str||'').trim().split(/\s+/);
  return (p[0]?.[0]||'') + (p[1]?.[0]||'') || '•';
};
const safeDate = v => { const d = v?new Date(v):null; return d && !isNaN(+d) ? d : null; };
const readJSON = (p, def) => { try { return JSON.parse(fs.readFileSync(p,'utf8')); } catch { return def; } };
const fileExists = p => { try { return fs.existsSync(p); } catch { return false; } };

// Read data
const ITEMS    = readJSON(ITEMS_PATH, { items: [] }).items || [];
const WIDGETS  = readJSON(WIDGETS_PATH, {});
const SCHEDULE = readJSON(SCHED_PATH, []);
const INSIDERS = readJSON(INS_PATH, []);
const ROSTER   = fileExists(ROSTER_PATH) ? readJSON(ROSTER_PATH, []) : [];
const OVERRIDES= readJSON(OVERRIDES_PATH, {});   // host -> local poster path

// ---------- artwork strategy: SSR posters only ----------
function posterForLink(link='') {
  try {
    const u = new URL(link);
    const host = u.hostname.toLowerCase();
    // try exact, then no-www
    if (OVERRIDES[host]) return OVERRIDES[host];
    const bare = host.replace(/^www\./,'');
    if (OVERRIDES[bare]) return OVERRIDES[bare];
  } catch {}
  return null;
}

function picturePoster({ link, label='', aspect='4x3', eager=false }) {
  const poster = posterForLink(link);
  const wh = aspect==='16x9' ? {w:1280,h:720} : {w:1200,h:900};

  if (poster) {
    // Direct local poster (SVG/PNG) — no remote fetches
    return `<img class="${aspect==='16x9'?'hero-img':'card-img'}" data-aspect="${aspect}" data-label="${esc(label)}"
             src="${esc(poster)}" alt="${esc(label)}" width="${wh.w}" height="${wh.h}"
             loading="${eager?'eager':'lazy'}" decoding="async">`;
  }

  // No mapping? Render initials tile so there's still art
  return `<div class="fallback-${aspect}"><div class="fallback-badge">${esc(initialsFrom(label))}</div></div>`;
}

// ---------- partition news / video ----------
const looksVideo = u => { try {const h=new URL(u).hostname; return /youtube\.com$|youtu\.be$/.test(h);} catch {return false;} };
const videoItems = ITEMS.filter(i => (i.type||'').toLowerCase()==='video' || looksVideo(i.link));
const newsItems  = ITEMS.filter(i => !((i.type||'').toLowerCase()==='video' || looksVideo(i.link)));

// Lead story (first news item)
const lead = newsItems[0] || null;

// News grid (next 11)
const newsGrid = newsItems.slice(lead?1:0, 12).map(i=>{
  const label = (i.source ? `${i.source}: ${i.title}` : i.title||'');
  const tier  = (i.tier||'').toLowerCase();
  const safeT = ['official','insiders','national'].includes(tier) ? tier : 'all';
  return `<article class="card" data-tier="${safeT}">
    <a class="card-img-wrap" href="${esc(i.link)}" target="_blank" rel="noopener">
      ${picturePoster({link:i.link,label,aspect:'4x3'})}
    </a>
    <div class="card-body">
      <a class="card-title" href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title||'')}</a>
    </div>
  </article>`;
}).join('');

// Videos (posters as well)
const videoGrid = videoItems.slice(0,9).map(v=>{
  const label = (v.source ? `${v.source}: ${v.title}` : v.title||'');
  return `<article class="card video-card">
    <a class="card-img-wrap" href="${esc(v.link)}" target="_blank" rel="noopener">
      ${picturePoster({link:v.link,label,aspect:'16x9'})}
    </a>
    <div class="card-body">
      <a class="card-title" href="${esc(v.link)}" target="_blank" rel="noopener">${esc(v.title||'')}</a>
    </div>
  </article>`;
}).join('');

// Ticker
const ticker = ITEMS.slice(0,12).map(i=>`<span style="margin:0 1.25rem">${esc(i.source||'')} — ${esc(i.title||'')}</span>`).join('');

// Schedule (upcoming + recent)
function parseGame(g){ const d=safeDate(g.utc||g.date); return d?{...g,_dt:d}:null; }
const games = (SCHEDULE||[]).map(parseGame).filter(Boolean);
const now = Date.now();
const upcoming = games.filter(g=>+g._dt>=now).sort((a,b)=>+a._dt-+b._dt).slice(0,6);
const recent   = games.filter(g=>+g._dt< now).sort((a,b)=>+b._dt-+a._dt).slice(0,5);
const fmtDay = dt => dt.toLocaleDateString([], {year:'numeric',month:'2-digit',day:'2-digit'});
const fmtTime= dt => dt.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});

const scheduleUpcomingHTML = upcoming.map(g=>{
  const dt=g._dt, day=fmtDay(dt), time=fmtTime(dt), site=(g.site||'TBD');
  return `<a class="game" href="${esc(g.espn_url||g.tickets_url||'#')}" target="_blank" rel="noopener">
    <div class="g-top"><span>${esc(day)}</span><span>${esc(time)} <small>local</small></span></div>
    <div class="g-title"><span class="logo-pill">${esc(initialsFrom(g.opp||''))}</span> ${esc(g.opp||'Opponent')} <span class="pill">${esc(site)}</span></div>
  </a>`;
}).join('');

const scheduleRecentHTML = recent.map(g=>{
  const day=fmtDay(g._dt); const opp=esc(g.opp||'Opponent'); const sc=esc(g.final_score||'');
  const outcome=(g.outcome||'').toUpperCase(); const wl = outcome==='W'?'win':(outcome==='L'?'loss':'');
  const recap=g.recap_url?`<a class="res-link" href="${esc(g.recap_url)}" target="_blank" rel="noopener">Recap</a>`:'';
  const box  =g.box_url?`<a class="res-link" href="${esc(g.box_url)}" target="_blank" rel="noopener">Box</a>`:'';
  return `<div class="result">
    <div class="res-line"><span class="res-date">${esc(day)}</span>${outcome?`<span class="wl-pill ${wl}">${outcome}</span>`:''}<span class="res-opp">${opp}</span>${sc?`<span class="res-score">${sc}</span>`:''}</div>
    <div class="res-meta">${recap}${box}</div>
  </div>`;
}).join('');

// Roster (headshots optional; if absent, SVG silhouette)
function rosterImg(p){
  const src=(p.headshot||'').trim();
  const label=`${p.name} (${p.pos})`;
  if (src) {
    return `<img class="player-img" src="${esc(src)}" alt="${esc(label)}" width="600" height="800" loading="lazy" decoding="async">`;
  }
  return `<svg class="player-img" aria-label="${esc(label)}" role="img" viewBox="0 0 600 800" xmlns="http://www.w3.org/2000/svg">
    <rect width="600" height="800" fill="#111"/>
    <circle cx="300" cy="240" r="110" fill="#1b1b1f"/>
    <rect x="150" y="360" width="300" height="260" rx="30" fill="#1b1b1f"/>
  </svg>`;
}
const rosterCards = (Array.isArray(ROSTER)?ROSTER:[]).map(p=>`
  <article class="player" tabindex="0" aria-label="${esc(p.name)}">
    ${rosterImg(p)}
    <div class="player-body">
      <div class="player-top"><div class="player-name">${esc(p.name)}</div><div class="player-num">#${esc(p.num)}</div></div>
      <div class="player-meta"><span>${esc(p.pos)}</span><span>${esc(p.ht)} • ${esc(p.wt)}</span><span>${esc(p.class)}</span></div>
      <div class="player-meta">${esc(p.hometown||'')}</div>
      ${p.bio?`<div class="player-bio">${esc(p.bio)}</div>`:''}
    </div>
  </article>
`).join('');

// Head/meta (no external JS needed for images anymore)
const META_IMG = 'static/logo.png';
const HEAD = `
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${esc(SITE_NAME)}</title>
<meta name="description" content="${esc(SITE_DESC)}"/>
<link rel="canonical" href="${SITE_URL}"/>
<meta property="og:image" content="${META_IMG}"/>
<link rel="icon" href="static/logo.png" type="image/png"/>
<link rel="apple-touch-icon" href="static/logo.png"/>
<link rel="stylesheet" href="static/css/pro.css?v=${ASSET_VER}"/>
`;

// Filter chips (URL sync preserved by runtime.js if you kept it; harmless if not)
const CHIPS = `
<div class="chips" data-filter-ready>
  <button class="chip is-active" data-filter="all" aria-pressed="true">All</button>
  <button class="chip" data-filter="official" aria-pressed="false">Official</button>
  <button class="chip" data-filter="insiders" aria-pressed="false">Insiders</button>
  <button class="chip" data-filter="national" aria-pressed="false">National</button>
</div>`;

// Hero (poster-based)
const heroHTML = lead ? `
<div id="hero" class="hero">
  <a href="${esc(lead.link)}" target="_blank" rel="noopener" class="hero-img-wrap">
    ${picturePoster({link:lead.link,label:(lead.source?`${lead.source}: ${lead.title}`:lead.title||''),aspect:'16x9',eager:true})}
  </a>
  <div class="hero-meta">
    <div class="pills">
      ${lead?.tier?`<span class="pill">${esc(lead.tier)}</span>`:''}
      ${lead?.source?`<span class="pill">${esc(lead.source)}</span>`:''}
    </div>
    <h3 class="hero-title"><a href="${esc(lead.link)}" target="_blank" rel="noopener">${esc(lead.title||'')}</a></h3>
  </div>
</div>` : '';

// Page HTML
const HTML = `<!doctype html>
<html lang="en">
<head>${HEAD}</head>
<body>
  <header class="topbar" role="banner">
    <a class="brand" href="./" aria-label="${esc(SITE_NAME)}">
      <div class="brand-line1">Team Hub</div>
      <div class="brand-line2">Boilermakers</div>
    </a>
  </header>

  <section class="ticker" aria-label="Top ticker" aria-live="polite">
    <div class="ticker-track">${ticker}</div>
  </section>

  <main class="container" role="main">
    <section id="news" class="panel" aria-labelledby="news-h">
      <div class="panel-hd"><h2 id="news-h">Top Headlines</h2>${CHIPS}</div>
      ${heroHTML}
      <div class="card-grid" id="news-grid">${newsGrid}</div>
    </section>

    <aside class="rail" aria-label="Sidebar">
      <section id="rankings" class="panel" aria-labelledby="rank-h">
        <div class="panel-hd"><h3 id="rank-h">Rankings</h3></div>
        <div class="rankings">
          <div class="rank-line"><span>AP Top 25:</span> <b>${WIDGETS.ap_rank ? `#${esc(WIDGETS.ap_rank)}` : '—'}</b> ${WIDGETS.ap_url?`<a href="${esc(WIDGETS.ap_url)}" target="_blank" rel="noopener">View</a>`:''}</div>
          <div class="rank-line"><span>KenPom:</span> <b>${WIDGETS.kenpom_rank ? `#${esc(WIDGETS.kenpom_rank)}` : '—'}</b> ${WIDGETS.kenpom_url?`<a href="${esc(WIDGETS.kenpom_url)}" target="_blank" rel="noopener">View</a>`:''}</div>
        </div>
      </section>

      <section id="schedule" class="panel" aria-labelledby="sched-h">
        <div class="panel-hd"><h3 id="sched-h">Upcoming Schedule</h3></div>
        <div class="schedule-list">${scheduleUpcomingHTML || '<div class="muted">No upcoming games</div>'}</div>
        <div class="panel-hd" style="margin-top:.75rem"><h3 id="results-h">Recent Results</h3></div>
        <div class="results-list">${scheduleRecentHTML || '<div class="muted">No recent games</div>'}</div>
      </section>

      <section id="insiders" class="panel" aria-labelledby="ins-h">
        <div class="panel-hd"><h3 id="ins-h">Insider / Beat Links</h3></div>
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

    <section id="roster" class="panel" aria-labelledby="roster-h">
      <div class="panel-hd"><h2 id="roster-h">Roster</h2></div>
      <div class="roster-grid">${rosterCards}</div>
    </section>

    <section id="videos" class="panel" aria-labelledby="vid-h">
      <div class="panel-hd"><h2 id="vid-h">Latest Videos</h2></div>
      <div class="video-grid">${videoGrid}</div>
    </section>
  </main>

  <footer class="footer" role="contentinfo">
    <div>Updated ${new Date().toLocaleString()}</div>
  </footer>

  <!-- keep runtime if you want URL-synced filters; harmless if absent -->
  <script src="static/js/runtime.js?v=${ASSET_VER}" defer></script>
</body>
</html>`;
fs.writeFileSync('index.html', HTML);
console.log('index.html built: SSR uses brand posters (no remote images)');