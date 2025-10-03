import fs from 'fs';
import path from 'path';

const ROOT = process.cwd();
const CACHE = path.join(ROOT, 'static/cache');
fs.mkdirSync(CACHE, { recursive: true });

function escapeHTML(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function initialsFrom(str=''){const p=(str||'').trim().split(/\s+/);return (p[0]?.[0]||'')+(p[1]?.[0]||'')||'•';}
function cachedThumb(source){
  const fname = (source||'src').toLowerCase().replace(/[^a-z0-9]+/g,'-')+'-thumb.jpg';
  return fs.existsSync(path.join(CACHE,fname)) ? `static/cache/${fname}` : null;
}

const items = JSON.parse(fs.readFileSync('static/teams/purdue-mbb/items.json','utf8')).items || [];
const widgets = JSON.parse(fs.readFileSync('static/widgets.json','utf8'));
const schedule = JSON.parse(fs.readFileSync('static/schedule.json','utf8'));
const insiders = JSON.parse(fs.readFileSync('static/insiders.json','utf8'));

// Build ticker
const ticker = items.slice(0,12).map(i=>`<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`).join('');

// Hero
const lead = items[0];
function imgTag(it,aspect='4x3'){
  const thumb = cachedThumb(it.source);
  if(thumb) return `<img class="card-img" src="${thumb}" alt="${escapeHTML(it.source||'')}" loading="lazy">`;
  return `<div class="fallback-${aspect}"><div class="fallback-badge">${escapeHTML(initialsFrom(it.source||''))}</div></div>`;
}
const hero = `
<div id="hero" class="hero">
  <a href="${lead.link}" target="_blank" class="hero-img-wrap">${imgTag(lead,'16x9')}</a>
  <div class="hero-meta">
    <div class="pills"><span class="pill">${escapeHTML(lead.tier||'')}</span><span class="pill">${escapeHTML(lead.source||'')}</span></div>
    <h3 class="hero-title"><a href="${lead.link}">${escapeHTML(lead.title||'')}</a></h3>
  </div>
</div>`;

// Cards
const grid = items.slice(1,12).map(i=>`
<article class="card">
  <a class="card-img-wrap" href="${i.link}">${imgTag(i)}</a>
  <div class="card-body"><a class="card-title" href="${i.link}">${escapeHTML(i.title||'')}</a></div>
</article>`).join('');

// Rankings
const rankings = `
<div class="rankings">
  <div class="rank-line"><span>AP Top 25:</span> <b>#${widgets.ap_rank}</b></div>
  <div class="rank-line"><span>KenPom:</span> <b>#${widgets.kenpom_rank}</b></div>
</div>`;

// Schedule
const schedHTML = schedule.slice(0,4).map(g=>`
<a class="game"><div class="g-title">${escapeHTML(g.opp||'Opponent')} <span class="pill">${g.site}</span></div></a>
`).join('');

// Insiders
const insidersHTML = insiders.map(o=>`
<a class="link-card" href="${o.latest_url||o.url}">
  <div class="link-body"><div class="link-title">${escapeHTML(o.name)}</div></div>
</a>`).join('');

// Final HTML
const html = `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Purdue MBB Hub</title>
<link rel="stylesheet" href="static/css/pro.css?v=ssr-auto"/>
</head><body>
<header class="topbar"><a class="brand" href="./"><div class="brand-line1">Team Hub</div><div class="brand-line2">Boilermakers</div></a></header>
<section class="ticker"><div class="ticker-track">${ticker}</div></section>
<main class="container">
<section id="news" class="panel"><h2>Top Headlines</h2>${hero}<div class="card-grid">${grid}</div></section>
<aside class="rail">
<section id="rankings" class="panel"><h3>Rankings</h3>${rankings}</section>
<section id="schedule" class="panel"><h3>Schedule</h3>${schedHTML}</section>
<section id="insiders" class="panel"><h3>Insiders</h3><div class="links-grid">${insidersHTML}</div></section>
</aside>
</main>
<footer class="footer"><div>Updated ${new Date().toLocaleString()}</div></footer>
<script src="static/js/runtime.js" defer></script>
</body></html>`;

fs.writeFileSync('index.html', html);
console.log('index.html rebuilt');