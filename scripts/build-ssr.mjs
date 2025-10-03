import fs from 'fs';
import path from 'path';

const CACHE = 'static/cache';
fs.mkdirSync(CACHE, { recursive: true });

function escapeHTML(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function initialsFrom(str=''){const p=(str||'').trim().split(/\s+/);return (p[0]?.[0]||'')+(p[1]?.[0]||'')||'•';}
function cachedThumb(source){
  const fname = (source||'src').toLowerCase().replace(/[^a-z0-9]+/g,'-')+'-thumb.jpg';
  return fs.existsSync(path.join(CACHE,fname)) ? `static/cache/${fname}` : null;
}

const itemsFile = 'static/teams/purdue-mbb/items.json';
const widgetsFile = 'static/widgets.json';
const scheduleFile = 'static/schedule.json';
const insidersFile = 'static/insiders.json';

const items = JSON.parse(fs.readFileSync(itemsFile,'utf8')).items || [];
const widgets = JSON.parse(fs.readFileSync(widgetsFile,'utf8'));
const schedule = JSON.parse(fs.readFileSync(scheduleFile,'utf8'));
const insiders = JSON.parse(fs.readFileSync(insidersFile,'utf8'));

function imgTag(it, aspect='4x3'){
  const thumb = cachedThumb(it.source);
  const cls = aspect==='16x9' ? 'hero-img' : 'card-img';
  if (thumb) {
    return `<img class="${cls}" data-aspect="${aspect}" data-label="${escapeHTML(it.source||'')}" src="${thumb}" alt="${escapeHTML(it.source||'')}" loading="${aspect==='16x9'?'eager':'lazy'}">`;
  }
  return `<div class="fallback-${aspect}"><div class="fallback-badge">${escapeHTML(initialsFrom(it.source||''))}</div></div>`;
}

// Separate video vs news
const videoItems = items.filter(i => (i.type||'').toLowerCase()==='video');
const newsItems  = items.filter(i => (i.type||'').toLowerCase()!=='video');

// Hero (news only)
const lead = newsItems[0];
const hero = lead ? `
<div id="hero" class="hero">
  <a href="${lead.link}" target="_blank" class="hero-img-wrap">${imgTag(lead,'16x9')}</a>
  <div class="hero-meta">
    <div class="pills">
      ${lead.tier?`<span class="pill">${escapeHTML(lead.tier)}</span>`:''}
      ${lead.source?`<span class="pill">${escapeHTML(lead.source)}</span>`:''}
    </div>
    <h3 class="hero-title"><a href="${lead.link}">${escapeHTML(lead.title||'')}</a></h3>
  </div>
</div>` : '';

// News cards (4:3)
const grid = newsItems.slice(1,12).map(i=>`
<article class="card">
  <a class="card-img-wrap" href="${i.link}" target="_blank" rel="noopener">${imgTag(i,'4x3')}</a>
  <div class="card-body"><a class="card-title" href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title||'')}</a></div>
</article>`).join('');

// Video cards (16:9)
const videoGrid = videoItems.slice(0,9).map(v=>`
<article class="card video-card">
  <a class="card-img-wrap" href="${v.link}" target="_blank" rel="noopener">${imgTag(v,'16x9')}</a>
  <div class="card-body"><a class="card-title" href="${v.link}" target="_blank" rel="noopener">${escapeHTML(v.title||'')}</a></div>
</article>`).join('');

// Rankings
const rankings = `
<div class="rankings">
  <div class="rank-line"><span>AP Top 25:</span> <b>#${widgets.ap_rank}</b></div>
  <div class="rank-line"><span>KenPom:</span> <b>#${widgets.kenpom_rank}</b></div>
</div>`;

// Schedule
const schedHTML = schedule.slice(0,6).map(g=>`
<a class="game"><div class="g-title">${escapeHTML(g.opp||'Opponent')} <span class="pill">${g.site}</span></div></a>`).join('');

// Insiders
const insidersHTML = insiders.map(o=>`
<a class="link-card" href="${o.latest_url||o.url}" target="_blank" rel="noopener">
  <div class="link-body"><div class="link-title">${escapeHTML(o.name)}</div>${o.latest_headline?`<div class="link-sub">${escapeHTML(o.latest_headline)}</div>`:''}</div>
</a>`).join('');

// Ticker (mixed)
const ticker = items.slice(0,12).map(i=>`<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`).join('');

// Final HTML
const html = `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Purdue MBB Hub</title>
<link rel="stylesheet" href="static/css/pro.css?v=ssr-auto"/>
</head><body>
<header class="topbar">
  <a class="brand" href="./">
    <div class="brand-line1">Team Hub</div>
    <div class="brand-line2">Boilermakers</div>
  </a>
</header>

<section class="ticker"><div class="ticker-track">${ticker}</div></section>

<main class="container">
  <section id="news" class="panel">
    <div class="panel-hd"><h2>Top Headlines</h2></div>
    ${hero}
    <div class="card-grid">${grid}</div>
  </section>

  <aside class="rail">
    <section id="rankings" class="panel"><div class="panel-hd"><h3>Rankings</h3></div>${rankings}</section>
    <section id="schedule" class="panel"><div class="panel-hd"><h3>Upcoming Schedule</h3></div><div class="schedule-list">${schedHTML}</div></section>
    <section id="insiders" class="panel"><div class="panel-hd"><h3>Insider / Beat Links</h3></div><div class="links-grid">${insidersHTML}</div></section>
  </aside>

  <section id="videos" class="panel">
    <div class="panel-hd"><h2>Latest Videos</h2></div>
    <div class="video-grid">${videoGrid}</div>
  </section>
</main>

<footer class="footer"><div>Updated ${new Date().toLocaleString()}</div></footer>
<script src="static/js/runtime.js" defer></script>
</body></html>`;

fs.writeFileSync('index.html', html);
console.log('index.html rebuilt with 16:9 videos + 4:3 news');