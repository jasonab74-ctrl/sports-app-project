import fs from 'fs';
import path from 'path';

const SITE_URL = 'https://jasonab74-ctrl.github.io/sports-app-project/';
const SITE_NAME = 'Purdue MBB Hub';
const SITE_DESC = 'Fast Purdue Men’s Basketball hub: top headlines, videos, rankings, schedule, insider links.';
const ASSET_VER = '20251004b'; // bumps CSS/JS to avoid stale cache

const CACHE_DIR      = 'static/cache';
const ITEMS_PATH     = 'static/teams/purdue-mbb/items.json';
const WIDGETS_PATH   = 'static/widgets.json';
const SCHED_PATH     = 'static/schedule.json';
const INS_PATH       = 'static/insiders.json';
const ROSTER_PATH    = 'static/teams/purdue-mbb/roster.json';
const OVERRIDES_PATH = 'static/image-overrides.json';

fs.mkdirSync(CACHE_DIR, { recursive: true });

/* ---------- helpers ---------- */
function escapeHTML(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function slugify(s=''){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'').slice(0,80)||'thumb';}
function initialsFrom(str=''){const p=(str||'').trim().split(/\s+/);return (p[0]?.[0]||'')+(p[1]?.[0]||'')||'•';}
function fileExists(p){ try{ return fs.existsSync(p); }catch{ return false; } }
function looksVideoLink(u=''){ try{const h=new URL(u).hostname;return /youtube\.com$|youtu\.be$/.test(h);}catch{return false;} }

/* cache hit by title */
function cachedBaseByTitle(title=''){
  const base = `${slugify(title)}-thumb`;
  const jpg = path.join(CACHE_DIR, `${base}.jpg`);
  const webp= path.join(CACHE_DIR, `${base}.webp`);
  const out = {};
  if (fileExists(jpg))  out.jpg  = `static/cache/${base}.jpg`;
  if (fileExists(webp)) out.webp = `static/cache/${base}.webp`;
  return (out.jpg || out.webp) ? out : null;
}
function overridesMap(){ try { return JSON.parse(fs.readFileSync(OVERRIDES_PATH,'utf8')); } catch { return {}; } }
function overrideFor(link=''){
  try { const host = new URL(link).hostname.toLowerCase(); const map = overridesMap(); return map[host] || null; }
  catch { return null; }
}
function isSVG(p=''){ return /\.svg(\?|$)/i.test(p); }

/* picture/img with inline onerror hook */
function pictureTag({srcs,label='',aspect='4x3',eager=false,altMode='simple'}){
  const wh = aspect==='16x9' ? {w:1280,h:720} : {w:1200,h:900};
  const alt = altMode==='detailed' ? label : (label || '');
  const cls = aspect==='16x9' ? 'hero-img' : 'card-img';
  const err = 'onerror="window.__imgErr&&window.__imgErr(this)"';
  if (!srcs || isSVG(srcs.jpg || srcs.webp || '')) {
    const single = srcs?.webp || srcs?.jpg || srcs || null;
    if (!single) return `<div class="fallback-${aspect}"><div class="fallback-badge">${escapeHTML(initialsFrom(label))}</div></div>`;
    return `<img class="${cls}" data-aspect="${aspect}" data-label="${escapeHTML(label)}"
             src="${escapeHTML(single)}" alt="${escapeHTML(alt)}" width="${wh.w}" height="${wh.h}"
             ${err} loading="${eager?'eager':'lazy'}" decoding="async">`;
  }
  const img = `<img class="${cls}" data-aspect="${aspect}" data-label="${escapeHTML(label)}"
                 src="${escapeHTML(srcs.jpg || srcs.webp)}" alt="${escapeHTML(alt)}" width="${wh.w}" height="${wh.h}"
                 ${err} loading="${eager?'eager':'lazy'}" decoding="async">`;
  const sourceWebp = srcs.webp ? `<source type="image/webp" srcset="${escapeHTML(srcs.webp)}">` : '';
  const sourceJpg  = srcs.jpg  ? `<source type="image/jpeg" srcset="${escapeHTML(srcs.jpg)}">` : '';
  return `<picture>${sourceWebp}${sourceJpg}${img}</picture>`;
}

/* ---------- data ---------- */
const itemsRaw   = JSON.parse(fs.readFileSync(ITEMS_PATH, 'utf8'));
const ITEMS      = (itemsRaw.items || itemsRaw || []).filter(Boolean);
const WIDGETS    = JSON.parse(fs.readFileSync(WIDGETS_PATH, 'utf8'));
const SCHEDULE   = JSON.parse(fs.readFileSync(SCHED_PATH, 'utf8'));
const INSIDERS   = JSON.parse(fs.readFileSync(INS_PATH, 'utf8'));
const ROSTER     = fileExists(ROSTER_PATH) ? JSON.parse(fs.readFileSync(ROSTER_PATH,'utf8')) : [];
const OVERRIDES  = overridesMap();

const videoItems = ITEMS.filter(i => (i.type||'').toLowerCase()==='video' || looksVideoLink(i.link));
const newsItems  = ITEMS.filter(i => !((i.type||'').toLowerCase()==='video' || looksVideoLink(i.link)));

function imgSourcesFor(item){
  const cached = cachedBaseByTitle(item.title);
  if (cached) return cached;
  const over = overrideFor(item.link);
  if (over) return { jpg: over };
  return null;
}

/* hero */
const lead = (() => { const withImg = newsItems.find(i => imgSourcesFor(i)); return withImg || newsItems[0] || null; })();
const leadSrcs = lead ? imgSourcesFor(lead) : null;

/* ----- news grid ----- */
const newsGrid = newsItems.slice(lead ? 1 : 0, 12).map(i=>{
  const srcs  = imgSourcesFor(i);
  const tier  = (i.tier || '').toLowerCase();
  const safeT = ['official','insiders','national'].includes(tier) ? tier : 'all';
  const label = (i.source ? `${i.source}: ${i.title}` : i.title || '');
  return `<article class="card" data-tier="${safeT}">
    <a class="card-img-wrap" href="${escapeHTML(i.link)}" target="_blank" rel="noopener">
      ${pictureTag({srcs,label,aspect:'4x3',altMode:'detailed'})}
    </a>
    <div class="card-body">
      <a class="card-title" href="${escapeHTML(i.link)}" target="_blank" rel="noopener">${escapeHTML(i.title||'')}</a>
    </div>
  </article>`;
}).join('');

/* videos */
const videoGrid = videoItems.slice(0, 9).map(v=>{
  const srcs = imgSourcesFor(v);
  const label = (v.source ? `${v.source}: ${v.title}` : v.title || '');
  return `<article class="card video-card">
    <a class="card-img-wrap" href="${escapeHTML(v.link)}" target="_blank" rel="noopener">
      ${pictureTag({srcs,label,aspect:'16x9',altMode:'detailed'})}
    </a>
    <div class="card-body">
      <a class="card-title" href="${escapeHTML(v.link)}" target="_blank" rel="noopener">${escapeHTML(v.title||'')}</a>
    </div>
  </article>`;
}).join('');

/* ticker */
const ticker = ITEMS.slice(0,12).map(i=>`<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`).join('');

/* inline handler */
const EARLY_HANDLER = `
<script>
  window.__imgOverrides = ${JSON.stringify(OVERRIDES)};
  window.__imgErr = function(img){
    try{
      var a = img.closest('a');
      var host = a ? new URL(a.href).hostname.toLowerCase() : '';
      var over = (window.__imgOverrides && window.__imgOverrides[host]) || null;
      if (over && img.getAttribute('data-__triedPoster')!=='1') {
        img.setAttribute('data-__triedPoster','1');
        img.removeAttribute('srcset');
        img.src = over;
        return;
      }
      var aspect = img.getAttribute('data-aspect') || '4x3';
      var label = img.getAttribute('data-label') || '';
      var wrap = document.createElement('div');
      wrap.className = 'fallback-' + aspect;
      var b = document.createElement('div');
      b.className = 'fallback-badge';
      b.textContent = (label.trim().split(/\\s+/)[0]||'').slice(0,1) + (label.trim().split(/\\s+/)[1]||'').slice(0,1) || '•';
      wrap.appendChild(b);
      img.replaceWith(wrap);
    }catch(e){img.style.display='none';}
  };
</script>`;

/* head */
const META_IMG = (leadSrcs?.webp || leadSrcs?.jpg || 'static/logo.png');
const HEAD = `
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${escapeHTML(SITE_NAME)}</title>
<meta name="description" content="${escapeHTML(SITE_DESC)}"/>
<link rel="canonical" href="${SITE_URL}"/>
<meta property="og:image" content="${META_IMG}"/>
<link rel="stylesheet" href="static/css/pro.css?v=${ASSET_VER}"/>
${EARLY_HANDLER}`;

/* chips */
const CHIPS = `
<div class="chips" data-filter-ready>
  <button class="chip is-active" data-filter="all" aria-pressed="true">All</button>
  <button class="chip" data-filter="official">Official</button>
  <button class="chip" data-filter="insiders">Insiders</button>
  <button class="chip" data-filter="national">National</button>
</div>`;

/* hero */
const heroHTML = lead ? `
<div id="hero" class="hero">
  <a href="${escapeHTML(lead.link)}" target="_blank" rel="noopener" class="hero-img-wrap">
    ${pictureTag({srcs:leadSrcs,label:(lead.source?`${lead.source}: ${lead.title}`:lead.title||''),aspect:'16x9',eager:true,altMode:'detailed'})}
  </a>
  <div class="hero-meta">
    <div class="pills">
      ${lead?.tier?`<span class="pill">${escapeHTML(lead.tier)}</span>`:''}
      ${lead?.source?`<span class="pill">${escapeHTML(lead.source)}</span>`:''}
    </div>
    <h3 class="hero-title"><a href="${escapeHTML(lead.link)}" target="_blank" rel="noopener">${escapeHTML(lead.title||'')}</a></h3>
  </div>
</div>` : '';

/* final HTML */
const HTML = `<!doctype html>
<html lang="en"><head>${HEAD}</head>
<body>
<header class="topbar"><a class="brand" href="./"><div class="brand-line1">Team Hub</div><div class="brand-line2">Boilermakers</div></a></header>
<section class="ticker" aria-live="polite"><div class="ticker-track">${ticker}</div></section>
<main class="container">
<section id="news" class="panel"><div class="panel-hd"><h2>Top Headlines</h2>${CHIPS}</div>${heroHTML}<div class="card-grid" id="news-grid">${newsGrid}</div></section>
<section id="videos" class="panel"><div class="panel-hd"><h2>Latest Videos</h2></div><div class="video-grid">${videoGrid}</div></section>
</main>
<footer class="footer"><div>Updated ${new Date().toLocaleString()}</div></footer>
</body></html>`;
fs.writeFileSync('index.html', HTML);
console.log('✅ index.html built with inline image error handler');