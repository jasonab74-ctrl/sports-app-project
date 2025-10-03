/**
 * Pre-renders index.html from repo JSON (no runtime fetches).
 * Inputs (must exist in repo):
 *   - static/teams/purdue-mbb/items.json
 *   - static/widgets.json
 *   - static/schedule.json
 *   - static/insiders.json
 * Output:
 *   - index.html (overwritten)
 */

import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';

const ROOT = process.cwd();
const PATH = (p) => path.join(ROOT, ...p.split('/'));

const TEAM = 'purdue-mbb';
const ITEMS_FILE = PATH('static/teams/purdue-mbb/items.json');
const WIDGETS_FILE = PATH('static/widgets.json');
const SCHEDULE_FILE = PATH('static/schedule.json');
const INSIDERS_FILE = PATH('static/insiders.json');

function readJSON(p, fallback = null) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); }
  catch { return fallback; }
}

function escapeHTML(s = '') {
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}

// ---------- Content helpers ----------
function timeAgo(iso) {
  try {
    const t = new Date(iso).getTime();
    const diff = (Date.now() - t) / 1000;
    if (!isFinite(diff) || diff < 0) return 'just now';
    const units = [
      ['y', 31536000], ['mo', 2592000], ['d', 86400],
      ['h', 3600], ['m', 60]
    ];
    for (const [label, sec] of units) {
      const v = Math.floor(diff / sec);
      if (v >= 1) return `${v}${label} ago`;
    }
    return 'just now';
  } catch { return 'just now'; }
}

function ytId(urlStr) {
  try {
    const u = new URL(urlStr);
    if (u.hostname.includes('youtu.be')) return u.pathname.slice(1);
    if (u.searchParams.get('v')) return u.searchParams.get('v');
    const m = /\/embed\/([^?]+)/.exec(u.pathname);
    return m ? m[1] : null;
  } catch { return null; }
}

function initialsFrom(str = '') {
  const parts = (str || '').trim().split(/\s+/);
  const a = (parts[0] || '')[0] || '';
  const b = (parts[1] || '')[0] || '';
  return (a + b).toUpperCase() || '•';
}

function imgTag({ src, aspect = '4x3', label = '' }) {
  if (!src) {
    return `<div class="fallback-${aspect}">
      <div class="fallback-badge">${escapeHTML(initialsFrom(label))}</div>
    </div>`;
  }
  return `<img class="${aspect === '16x9' ? 'hero-img' : 'card-img'}"
              data-aspect="${aspect}"
              data-label="${escapeHTML(label)}"
              src="${escapeHTML(src)}"
              alt=""
              loading="${aspect === '16x9' ? 'eager' : 'lazy'}"
              decoding="async"
              crossorigin="anonymous">`;
}

function heroHTML(lead) {
  if (!lead) return '';
  const yt = ytId(lead.link || '');
  const src = yt ? `https://i.ytimg.com/vi/${yt}/hqdefault.jpg` : (lead.image || '');
  const label = lead.source || lead.title || '';
  const tier = (lead.tier || lead.tag || '').toLowerCase();
  const pill = tier ? `<span class="pill">${escapeHTML(tier)}</span>` : '';
  const when = timeAgo(lead.date || lead.published || new Date().toISOString());
  return `
  <div id="hero" class="hero">
    <a href="${escapeHTML(lead.link)}" target="_blank" rel="noopener" class="hero-img-wrap">
      ${imgTag({ src, aspect: '16x9', label })}
    </a>
    <div class="hero-meta">
      <div class="pills">
        ${pill}
        <span class="pill">${escapeHTML(lead.source || '')}</span>
        <span class="pill">${when}</span>
      </div>
      <h3 class="hero-title"><a href="${escapeHTML(lead.link)}" target="_blank" rel="noopener">${escapeHTML(lead.title || '')}</a></h3>
      <div class="hero-sub">${escapeHTML(lead.summary || '')}</div>
    </div>
  </div>`;
}

function cardHTML(i) {
  const yt = ytId(i.link || '');
  const src = yt ? `https://i.ytimg.com/vi/${yt}/hqdefault.jpg` : (i.image || '');
  const label = i.source || i.title || '';
  const when = timeAgo(i.date || i.published || new Date().toISOString());
  const tier = (i.tier || i.tag || '').toLowerCase();
  const pill = tier ? `<span class="pill">${escapeHTML(tier)}</span>` : '';
  return `
  <article class="card">
    <a class="card-img-wrap" href="${escapeHTML(i.link)}" target="_blank" rel="noopener">
      ${imgTag({ src, aspect: '4x3', label })}
    </a>
    <div class="card-body">
      <div class="card-meta">${pill} <span>${escapeHTML(i.source || '')}</span> • <span>${when}</span></div>
      <a class="card-title" href="${escapeHTML(i.link)}" target="_blank" rel="noopener">${escapeHTML(i.title || '')}</a>
    </div>
  </article>`;
}

function scheduleRow(g) {
  const dt = new Date(g.utc || g.date);
  const day = dt.toLocaleDateString([], { year: 'numeric', month: '2-digit', day: '2-digit' });
  const time = dt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const site = (g.site || 'TBD').toLowerCase();
  const siteCls = site.startsWith('home') ? 'site-home' : site.startsWith('away') ? 'site-away' : site.startsWith('neutral') ? 'site-neutral' : '';
  return `
  <a class="game ${siteCls}" href="${escapeHTML(g.espn_url || '#')}" target="_blank" rel="noopener">
    <div class="g-top"><span>${escapeHTML(day)}</span><span>${escapeHTML(time)} <small>local</small></span></div>
    <div class="g-title"><span class="logo-pill">${escapeHTML(initialsFrom(g.opp || ''))}</span> ${escapeHTML(g.opp || 'Opponent')} <span class="pill">${escapeHTML(g.site || 'TBD')}</span></div>
  </a>`;
}

function insiderCard(o) {
  const sub = o.latest_headline ? `<div class="link-sub">${escapeHTML(o.latest_headline)}</div>` : '';
  return `
  <a class="link-card" href="${escapeHTML(o.latest_url || o.url)}" target="_blank" rel="noopener">
    <div class="link-logo">📰</div>
    <div class="link-body"><div class="link-title">${escapeHTML(o.name)}</div>${sub}</div>
    <div class="link-meta">${escapeHTML(o.type || '')}${o.pay ? ' <span class="badge-pay">$</span>' : ''}</div>
  </a>`;
}

// ---------- Load data from repo ----------
const itemsData = readJSON(ITEMS_FILE, { items: [] });
const items = (Array.isArray(itemsData) ? itemsData : itemsData.items) || [];

const widgets = readJSON(WIDGETS_FILE, { ap_rank: null, kenpom_rank: null, ap_url: '#', kenpom_url: '#', updated_at: null });
const schedule = readJSON(SCHEDULE_FILE, []);
const insiders = readJSON(INSIDERS_FILE, []);

// ---------- Ticker ----------
const tickerItems = items.slice(0, 12).map(i => `<span style="margin:0 1.25rem">${escapeHTML(i.source || '')} — ${escapeHTML(i.title || '')}</span>`).join('');

// ---------- Hero + Grid ----------
const hero = heroHTML(items[0]);
const grid = items.slice(1, 19).map(cardHTML).join('');

// ---------- Rankings ----------
const updatedTxt = widgets.updated_at ? new Date(widgets.updated_at).toLocaleString([], { month: 'short', day: 'numeric' }) : '';

const rankingsHTML = `
<div class="rankings">
  <div class="rank-line"><span>AP Top 25:</span> <b>${widgets.ap_rank ? `#${widgets.ap_rank}` : '—'}</b> <a href="${escapeHTML(widgets.ap_url || '#')}" target="_blank" rel="noopener">View</a></div>
  <div class="rank-line"><span>KenPom:</span> <b>${widgets.kenpom_rank ? `#${widgets.kenpom_rank}` : '—'}</b> <a href="${escapeHTML(widgets.kenpom_url || '#')}" target="_blank" rel="noopener">View</a></div>
  <div class="rank-updated">${updatedTxt ? `as of ${escapeHTML(updatedTxt)}` : ''}</div>
</div>`;

// ---------- Schedule ----------
const scheduleHTML = (schedule || []).slice(0, 6).map(scheduleRow).join('');

// ---------- Insiders ----------
const insidersHTML = (insiders || []).map(insiderCard).join('');

// ---------- Compose HTML ----------
const HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Team Hub — Purdue Men's Basketball</title>
  <meta name="theme-color" content="#0c0c0e"/>
  <link rel="preconnect" href="https://i.ytimg.com">
  <link rel="preconnect" href="https://img.si.com">
  <link rel="preconnect" href="https://gannett-cdn.com">
  <link rel="preconnect" href="https://247sports.imgix.net">
  <link rel="preconnect" href="https://espncdn.com">
  <link rel="preconnect" href="https://s.yimg.com">
  <link rel="stylesheet" href="static/css/pro.css?v=ssr-auto"/>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="./">
      <div class="brand-logo-wrap">
        <img class="brand-logo" src="static/logo.png" alt="Purdue" onerror="this.style.display='none';this.nextElementSibling.hidden=false;">
        <div class="brand-fallback" hidden>🏀</div>
      </div>
      <div>
        <div class="brand-line1">Team Hub</div>
        <div class="brand-line2">Boilermakers</div>
      </div>
    </a>
    <nav class="nav">
      <a href="#news">News</a>
      <a href="#videos">Videos</a>
      <a href="#rankings">Rankings</a>
      <a href="#schedule">Schedule</a>
      <a href="#nil">NIL</a>
    </nav>
  </header>

  <section class="ticker" aria-label="Top ticker">
    <div class="ticker-track">
      ${tickerItems}
    </div>
  </section>

  <main class="container">
    <section id="news" class="panel">
      <div class="panel-hd">
        <h2>Top Headlines</h2>
        <div class="panel-actions">
          <button class="pill pill-all">All</button>
          <button class="pill">Official</button>
          <button class="pill">Insiders</button>
          <button class="pill">National</button>
        </div>
      </div>
      ${hero}
      <div id="headlines" class="card-grid">
        ${grid}
      </div>
    </section>

    <aside class="rail">
      <section id="rankings" class="panel">
        <div class="panel-hd"><h3>Rankings</h3></div>
        ${rankingsHTML}
      </section>

      <section id="schedule" class="panel">
        <div class="panel-hd"><h3>Upcoming Schedule</h3></div>
        <div class="schedule-list">
          ${scheduleHTML}
        </div>
      </section>

      <section id="insiders" class="panel">
        <div class="panel-hd"><h3>Insider / Beat Links</h3>
          <div class="panel-actions">
            <button class="pill pill-all">All</button>
            <button class="pill">Official</button>
            <button class="pill">Insiders</button>
          </div>
        </div>
        <div class="links-grid">
          ${insidersHTML}
        </div>
      </section>

      <section id="nil" class="panel">
        <div class="panel-hd"><h3>NIL Leaderboard</h3></div>
        <ol class="nil">
          <li><b>Top Player A</b> — $1.2M est.</li>
          <li><b>Top Player B</b> — $900k est.</li>
          <li><b>Top Player C</b> — $700k est.</li>
        </ol>
      </section>
    </aside>

    <section id="videos" class="panel">
      <div class="panel-hd">
        <h2>Latest Videos</h2>
        <div class="panel-actions">
          <button class="pill pill-all">All</button>
          <button class="pill">Official</button>
          <button class="pill">Insiders</button>
        </div>
      </div>
      <div class="video-grid"></div>
    </section>
  </main>

  <footer class="footer">
    <div>
      <span>Updated ${new Date().toLocaleString([], {hour:'2-digit', minute:'2-digit'})}</span>
      ${itemsData?.sources ? `<span>• ${escapeHTML(String(itemsData.sources.length))} sources</span>` : ''}
    </div>
  </footer>

  <script src="static/js/runtime.js?v=ssr-auto" defer></script>
</body>
</html>
`;

// ---------- Write out ----------
fs.writeFileSync(PATH('index.html'), HTML);
console.log('index.html generated from JSON.');