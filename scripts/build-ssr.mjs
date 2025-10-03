import fs from 'fs';
import path from 'path';

const SITE_URL = 'https://jasonab74-ctrl.github.io/sports-app-project/';
const SITE_NAME = 'Purdue MBB Hub';
const SITE_DESC = 'Fast Purdue Men’s Basketball hub: top headlines, videos, rankings, schedule, insider links.';

const CACHE_DIR   = 'static/cache';
const ITEMS_PATH  = 'static/teams/purdue-mbb/items.json';
const WIDGETS_PATH= 'static/widgets.json';
const SCHED_PATH  = 'static/schedule.json';
const INS_PATH    = 'static/insiders.json';
const OVERRIDES_PATH = 'static/image-overrides.json';

fs.mkdirSync(CACHE_DIR, { recursive: true });

function escapeHTML(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function slugify(s=''){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'').slice(0,80) || 'thumb';}
function initialsFrom(str=''){const p=(str||'').trim().split(/\s+/);return (p[0]?.[0]||'')+(p[1]?.[0]||'')||'•';}
function youtubeLikeUrl(u=''){ try{const h=new URL(u).hostname;return /youtube\.com$|youtu\.be$/.test(h);}catch{return false;} }
function looksVideoLink(u=''){ return youtubeLikeUrl(u) || /\/video\//i.test(u||''); }

function cachedThumbByTitle(title=''){
  const fname = `${slugify(title)}-thumb.jpg`;
  const p = path.join(CACHE_DIR, fname);
  return fs.existsSync(p) ? `static/cache/${fname}` : null;
}
function overridesMap(){
  try { return JSON.parse(fs.readFileSync(OVERRIDES_PATH,'utf8')); } catch { return {}; }
}
function overrideFor(link=''){
  try {
    const host = new URL(link).hostname.toLowerCase();
    const map = overridesMap();
    return map[host] || null;
  } catch { return null; }
}

function imgTag({src,label='',aspect='4x3',eager=false}){
  const wh = aspect==='16x9' ? {w:1280,h:720} : {w:1200,h:900};
  if (src) {
    return `<img class="${aspect==='16x9'?'hero-img':'card-img'}" data-aspect="${aspect}" data-label="${escapeHTML(label)}"
             src="${escapeHTML(src)}" alt="${escapeHTML(label)}" width="${wh.w}" height="${wh.h}"
             loading="${eager?'eager':'lazy'}" decoding="async">`;
  }
  return `<div class="fallback-${aspect}"><div class="fallback-badge">${escapeHTML(initialsFrom(label))}</div></div>`;
}

/* ===== Load data ===== */
const itemsRaw = JSON.parse(fs.readFileSync(ITEMS_PATH, 'utf8'));
const ITEMS = (itemsRaw.items || itemsRaw || []).filter(Boolean);
const WIDGETS = JSON.parse(fs.readFileSync(WIDGETS_PATH, 'utf8'));
const SCHEDULE = JSON.parse(fs.readFileSync(SCHED_PATH, 'utf8'));
const INSIDERS = JSON.parse(fs.readFileSync(INS_PATH, 'utf8'));

/* ===== Smart video separation ===== */
const videoItems = ITEMS.filter(i => (i.type||'').toLowerCase()==='video' || looksVideoLink(i.link));
const newsItems  = ITEMS.filter(i => !((i.type||'').toLowerCase()==='video' || looksVideoLink(i.link)));

/* ===== Hero ===== */
const lead = newsItems[0];
const leadThumb = lead ? (cachedThumbByTitle(lead.title) || overrideFor(lead.link)) : null;
const heroHTML = lead ? `
<div id="hero" class="hero">
  <a href="${escapeHTML(lead.link)}" target="_blank" rel="noopener" class="hero-img-wrap">
    ${imgTag({src:leadThumb,label:lead.source||lead.title,aspect:'16x9',eager:true})}
  </a>
  <div class="hero-meta">
    <div class="pills">
      ${lead.tier?`<span class="pill">${escapeHTML(lead.tier)}</span>`:''}
      ${lead.source?`<span class="pill">${escapeHTML(lead.source)}</span>`:''}
    </div>
    <h3 class="hero-title"><a href="${escapeHTML(lead.link)}" target="_blank" rel="noopener">${escapeHTML(lead.title||'')}</a></h3>
  </div>
</div>` : '';

/* ===== News grid ===== */
const newsGrid = newsItems.slice(1, 12).map(i=>{
  const src = cachedThumbByTitle(i.title) || overrideFor(i.link);
  return `<article class="card">
    <a class="card-img-wrap" href="${escapeHTML(i.link)}" target="_blank" rel="noopener">
      ${imgTag({src,label:i.source||i.title,aspect:'4x3'})}
    </a>
    <div class="card-body">
      <a class="card-title" href="${escapeHTML(i.link)}" target="_blank" rel="noopener">${escapeHTML(i.title||'')}</a>
    </div>
  </article>`;
}).join('');

/* ===== Videos ===== */
const videoGrid = videoItems.slice(0, 9).map(v=>{
  const src = cachedThumbByTitle(v.title) || overrideFor(v.link);
  return `<article class="card video-card">
    <a class="card-img-wrap" href="${escapeHTML(v.link)}" target="_blank" rel="noopener">
      ${imgTag({src,label:v.source||v.title,aspect:'16x9'})}
    </a>
    <div class="card-body">
      <a class="card-title" href="${escapeHTML(v.link)}" target="_blank" rel="noopener">${escapeHTML(v.title||'')}</a>
    </div>
  </article>`;
}).join('');

/* ===== Panels & Meta (unchanged) ===== */
const rankingsHTML = `
<div class="rankings">
  <div class="rank-line"><span>AP Top 25:</span> <b>${WIDGETS.ap_rank ? `#${WIDGETS.ap_rank}` : '—'}</b> ${WIDGETS.ap_url?`<a href="${escapeHTML(WIDGETS.ap_url)}" target="_blank" rel="noopener">View</a>`:''}</div>
  <div class="rank-line"><span>KenPom:</span> <b>${WIDGETS.kenpom_rank ? `#${WIDGETS.kenpom_rank}` : '—'}</b> ${WIDGETS.kenpom_url?`<a href="${escapeHTML(WIDGETS.kenpom_url)}" target="_blank" rel="noopener">View</a>`:''}</div>
  <div class="rank-updated">${WIDGETS.updated_at ? `as of ${escapeHTML(new Date(WIDGETS.updated_at).toLocaleString([], {month:'short', day:'numeric'}) )}` : ''}</div>
</div>`;

const scheduleHTML = (SCHEDULE||[]).slice(0,6).map(g=>{
  const dt=new Date(g.utc||g.date);
  const day=dt.toLocaleDateString([], {year:'numeric',month:'2-digit',day:'2-digit'});
  const time=dt.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
  const site=(g.site||'TBD');
  return `<a class="game" href="${escapeHTML(g.espn_url||'#')}" target="_blank" rel="noopener">
    <div class="g-top"><span>${escapeHTML(day)}</span><span>${escapeHTML(time)} <small>local</small></span></div>
    <div class="g-title"><span class="logo-pill">${escapeHTML(initialsFrom(g.opp||''))}</span> ${escapeHTML(g.opp||'Opponent')} <span class="pill">${escapeHTML(site)}</span></div>
  </a>`;
}).join('');

const insidersHTML = (INSIDERS||[]).map(o=>`
  <a class="link-card" href="${escapeHTML(o.latest_url||o.url)}" target="_blank" rel="noopener">
    <div class="link-logo">📰</div>
    <div class="link-body">
      <div class="link-title">${escapeHTML(o.name)}</div>
      ${o.latest_headline?`<div class="link-sub">${escapeHTML(o.latest_headline)}</div>`:''}
    </div>
    <div class="link-meta">${escapeHTML(o.type||'')}${o.pay?' <span class="badge-pay">$</span>':''}</div>
  </a>
`).join('');

const ticker = ITEMS.slice(0,12).map(i=>`<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`).join('');

const META_IMG = leadThumb || 'static/logo.png';
const HEAD_META = `
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${escapeHTML(SITE_NAME)}</title>
<meta name="description" content="${escapeHTML(SITE_DESC)}"/>
<link rel="canonical" href="${SITE_URL}"/>

<meta property="og:type" content="website"/>
<meta property="og:site_name" content="${escapeHTML(SITE_NAME)}"/>
<meta property="og:title" content="${escapeHTML(SITE_NAME)}"/>
<meta property="og:description" content="${escapeHTML(SITE_DESC)}"/>
<meta property="og:url" content="${SITE_URL}"/>
<meta property="og:image" content="${META_IMG}"/>

<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="${escapeHTML(SITE_NAME)}"/>
<meta name="twitter:description" content="${escapeHTML(SITE_DESC)}"/>
<meta name="twitter:image" content="${META_IMG}"/>

<link rel="icon" href="static/logo.png" type="image/png"/>
<link rel="apple-touch-icon" href="static/logo.png"/>
<link rel="preconnect" href="https://i.ytimg.com"/>
<link rel="preconnect" href="https://img.si.com"/>
<link rel="preconnect" href="https://gannett-cdn.com"/>
<link rel="preconnect" href="https://247sports.imgix.net"/>
<link rel="preconnect" href="https://espncdn.com"/>
<link rel="preconnect" href="https://s.yimg.com"/>

<link rel="stylesheet" href="static/css/pro.css?v=ssr-auto"/>
`;

const HTML = `<!doctype html>
<html lang="en">
<head>
${HEAD_META}
</head>
<body>
  <header class="topbar" role="banner">
    <a class="brand" href="./" aria-label="${escapeHTML(SITE_NAME)}">
      <div class="brand-line1">Team Hub</div>
      <div class="brand-line2">Boilermakers</div>
    </a>
  </header>

  <section class="ticker" aria-label="Top ticker"><div class="ticker-track">${ticker}</div></section>

  <main class="container" role="main">
    <section id="news" class="panel" aria-labelledby="news-h">
      <div class="panel-hd"><h2 id="news-h">Top Headlines</h2></div>
      ${heroHTML}
      <div class="card-grid">${newsGrid}</div>
    </section>

    <aside class="rail" aria-label="Sidebar">
      <section id="rankings" class="panel" aria-labelledby="rank-h">
        <div class="panel-hd"><h3 id="rank-h">Rankings</h3></div>
        ${rankingsHTML}
      </section>
      <section id="schedule" class="panel" aria-labelledby="sched-h">
        <div class="panel-hd"><h3 id="sched-h">Upcoming Schedule</h3></div>
        <div class="schedule-list">${scheduleHTML}</div>
      </section>
      <section id="insiders" class="panel" aria-labelledby="ins-h">
        <div class="panel-hd"><h3 id="ins-h">Insider / Beat Links</h3></div>
        <div class="links-grid">${insidersHTML}</div>
      </section>
    </aside>

    <section id="videos" class="panel" aria-labelledby="vid-h">
      <div class="panel-hd"><h2 id="vid-h">Latest Videos</h2></div>
      <div class="video-grid">${videoGrid}</div>
    </section>
  </main>

  <footer class="footer" role="contentinfo">
    <div>Updated ${new Date().toLocaleString()}</div>
  </footer>

  <script src="static/js/kill-sw.js" defer></script>
  <script src="static/js/runtime.js" defer></script>
</body>
</html>`;

fs.writeFileSync('index.html', HTML);
console.log('index.html rebuilt with domain overrides');