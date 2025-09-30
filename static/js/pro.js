/* Core App JS — hamburger, ticker, carousel, data rendering, encoding fix */

const qs = (s, el = document) => el.querySelector(s);
const qsa = (s, el = document) => [...el.querySelectorAll(s)];
const state = {
  teamSlug: new URL(location.href).searchParams.get('team') || 'purdue-mbb',
  items: [],
  videos: [],
  team: null,
  widgets: null,
  schedule: null
};

const paths = {
  team: 'static/team.json',
  items: (slug) => `static/teams/${slug}/items.json`,
  widgets: 'static/widgets.json',
  schedule: 'static/schedule.json',
  sources: 'static/sources.json'
};

// ---- Utility: decode HTML entities (fixes &#8211; etc.)
function decodeEntities(str) {
  if (!str) return '';
  const txt = document.createElement('textarea');
  txt.innerHTML = str;
  return txt.value;
}

// ---- Drawer / Hamburger
function initDrawer() {
  const drawer = qs('#drawer');
  const openBtn = qs('#hamburger');
  const closeBtn = qs('#drawer-close');

  const open = () => {
    drawer.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
  };
  const close = () => {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
  };

  openBtn.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  drawer.addEventListener('click', (e) => {
    if (e.target.matches('a')) close();
  });
}

// ---- Tabs
function initTabs() {
  qsa('.tabs .chip').forEach(btn => {
    btn.addEventListener('click', () => {
      qsa('.tabs .chip').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      qsa('.tab').forEach(sec => sec.classList.remove('visible'));
      qs('#' + tab).classList.add('visible');
    });
  });
}

// ---- Ticker
function renderTicker(items) {
  const track = qs('#ticker-track');
  const headlines = items.slice(0, 12)
    .map(i => `<a href="${i.url}" target="_blank" rel="noopener">${decodeEntities(i.title)}</a>`);
  // Duplicate to create seamless marquee
  track.innerHTML = [...headlines, ...headlines].join(' • ');
  const totalWidth = track.scrollWidth / 2;
  const duration = Math.max(20, Math.min(60, Math.round(totalWidth / 30))); // seconds
  track.style.animation = `marquee ${duration}s linear infinite`;

  // tap-to-pause on touch
  let tapped = false;
  qs('#ticker').addEventListener('touchstart', () => {
    tapped = !tapped;
    qs('#ticker').classList.toggle('tapped', tapped);
  }, {passive:true});
}

// ---- Carousel
function renderCarousel(items) {
  const el = qs('#carousel');
  el.innerHTML = '';
  items.slice(0, 8).forEach(i => el.appendChild(makeCard(i)));
  // auto-snap scroll
  let autoScroll;
  const start = () => {
    stop();
    autoScroll = setInterval(() => {
      el.scrollBy({left: el.clientWidth * 0.8, behavior: 'smooth'});
      if (el.scrollLeft + el.clientWidth >= el.scrollWidth - 8) {
        el.scrollTo({left: 0, behavior: 'smooth'});
      }
    }, 4500);
  };
  const stop = () => autoScroll && clearInterval(autoScroll);
  el.addEventListener('mouseenter', stop);
  el.addEventListener('mouseleave', start);
  el.addEventListener('touchstart', stop, {passive:true});
  el.addEventListener('touchend', start, {passive:true});
  start();
}

// ---- Card factory
function makeCard(item) {
  const a = document.createElement('a');
  a.className = 'card';
  a.href = item.url;
  a.target = '_blank';
  a.rel = 'noopener';

  const thumb = document.createElement('div');
  thumb.className = 'card__thumb';
  const img = document.createElement('img');
  img.loading = 'lazy';
  img.src = item.image || item.thumbnail || '';
  img.alt = decodeEntities(item.title);
  thumb.appendChild(img);

  const body = document.createElement('div');
  body.className = 'card__body';
  const kicker = document.createElement('div');
  kicker.className = 'card__kicker';
  kicker.textContent = item.tag || item.type || (item.is_video ? 'Video' : 'News');

  const title = document.createElement('div');
  title.className = 'card__title';
  title.textContent = decodeEntities(item.title);

  const meta = document.createElement('div');
  meta.className = 'card__meta';
  const date = item.date ? new Date(item.date) : null;
  const datestr = date ? date.toLocaleDateString(undefined, {month:'short', day:'numeric'}) : '';
  meta.textContent = [item.source || '', datestr].filter(Boolean).join(' • ');

  body.appendChild(kicker); body.appendChild(title); body.appendChild(meta);
  a.appendChild(thumb); a.appendChild(body);
  return a;
}

// ---- Render grids
function renderNews(items) {
  const grid = qs('#news-grid');
  grid.innerHTML = '';
  items.slice(0, 24).forEach(i => grid.appendChild(makeCard(i)));
}
function renderVideos(items) {
  const grid = qs('#video-grid');
  grid.innerHTML = '';
  items.filter(i => i.is_video).slice(0, 24).forEach(i => grid.appendChild(makeCard(i)));
}

// ---- Sidebar widgets
function renderRankings(widgets) {
  const el = qs('#rankings-body');
  el.innerHTML = '';
  const rows = [
    ['AP Rank', widgets.ap_rank ?? '—'],
    ['KenPom', widgets.kenpom ?? '—'],
    ['NET', widgets.net ?? '—']
  ];
  const ul = document.createElement('ul'); ul.className = 'list';
  rows.forEach(([k,v]) => {
    const li = document.createElement('li');
    const l = document.createElement('span'); l.textContent = k;
    const r = document.createElement('strong'); r.textContent = v;
    li.append(l,r); ul.appendChild(li);
  });
  el.appendChild(ul);
}

function renderSchedule(schedule) {
  const el = qs('#schedule-body'); el.innerHTML='';
  const now = new Date();
  const upcoming = schedule.games
    .filter(g => new Date(g.date) >= now)
    .sort((a,b) => new Date(a.date) - new Date(b.date))
    .slice(0,6);
  if (upcoming.length === 0) {
    el.innerHTML = '<div class="muted">No upcoming games.</div>'; return;
  }
  const ul = document.createElement('ul'); ul.className='list';
  upcoming.forEach(g => {
    const li = document.createElement('li');
    const left = document.createElement('span');
    const right = document.createElement('span');
    const d = new Date(g.date);
    left.textContent = d.toLocaleDateString(undefined,{month:'short', day:'numeric'}) + ' • ' + g.opponent;
    right.textContent = g.venue || (g.home ? 'Home' : 'Away');
    li.append(left,right); ul.appendChild(li);
  });
  el.appendChild(ul);
}

function renderNIL(widgets) {
  const el = qs('#nil-body'); el.innerHTML='';
  const list = document.createElement('ul'); list.className='list';
  (widgets.nil || []).slice(0,5).forEach(p => {
    const li = document.createElement('li');
    const left = document.createElement('span'); left.textContent = p.name;
    const right = document.createElement('span'); right.textContent = p.value;
    li.append(left,right); list.appendChild(li);
  });
  if ((widgets.nil || []).length === 0) {
    el.innerHTML = '<div class="muted">NIL data not available.</div>';
  } else {
    el.appendChild(list);
  }
}
function renderInsider(widgets) {
  const el = qs('#insider-body'); el.innerHTML='';
  const list = document.createElement('ul'); list.className='list';
  (widgets.insider || []).forEach(link => {
    const li = document.createElement('li');
    const a = document.createElement('a'); a.href = link.url; a.target='_blank'; a.rel='noopener'; a.textContent=link.name;
    const r = document.createElement('span'); r.textContent = link.note || '';
    li.append(a,r); list.appendChild(li);
  });
  el.appendChild(list);
}

// ---- Theme
function applyTheme(team) {
  document.title = `${team.name} — Team Hub`;
  qs('#site-title').textContent = team.name;
  qs('#team-logo').src = team.logo;
  qs('#drawer-team-name').textContent = team.name;
  document.documentElement.style.setProperty('--accent', team.colors.accent);
  document.documentElement.style.setProperty('--bg', team.colors.bg);
  document.documentElement.style.setProperty('--card', team.colors.card);
}

// ---- Fetch JSON + render
async function loadJSON(url) {
  const r = await fetch(url, {cache:'no-store'});
  if (!r.ok) throw new Error(`Failed to fetch ${url}`);
  return r.json();
}

async function boot() {
  initDrawer();
  initTabs();

  try {
    state.team = await loadJSON(paths.team);
    const teamCfg = state.team.teams[state.teamSlug] || Object.values(state.team.teams)[0];
    applyTheme(teamCfg);

    const [items, widgets, schedule] = await Promise.all([
      loadJSON(paths.items(state.teamSlug)).catch(()=>({items:[]})),
      loadJSON(paths.widgets).catch(()=>({})),
      loadJSON(paths.schedule).catch(()=>({games:[]}))
    ]);

    state.items = (items.items || []).map(i => ({...i, title: decodeEntities(i.title)}));
    state.widgets = widgets[ state.teamSlug ] || widgets.default || {};
    state.schedule = schedule[ state.teamSlug ] || schedule;

    // Split videos/news
    state.videos = state.items.filter(i => i.is_video);
    const news = state.items.filter(i => !i.is_video);

    renderTicker(state.items);
    renderCarousel(news.length ? news : state.items);
    renderNews(news.length ? news : state.items);
    renderVideos(state.videos);
    renderRankings(state.widgets);
    renderSchedule(state.schedule);
    renderNIL(state.widgets);
    renderInsider(state.widgets);
  } catch (e) {
    console.error(e);
  }

  // Manual refresh (re-fetch)
  qs('#refresh').addEventListener('click', () => location.reload());
}

document.addEventListener('DOMContentLoaded', boot);
