// app.js — stable, subpath-safe (RELATIVE paths only)
(() => {
  const BASE = "./"; // ✅ works at any project subpath
  const url = (p) => BASE + p.replace(/^\//, "");
  const byId = (id) => document.getElementById(id);

  const esc = (s='') => (s+'').replace(/[&<>"']/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  const pill = (t) => t ? `<span class="pill">${esc(t)}</span>` : '';

  const posterSVG = (l1='News', l2='') =>
    `<svg viewBox="0 0 800 450" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#202631"/><stop offset="1" stop-color="#0d1117"/></linearGradient></defs><rect fill="url(#g)" width="100%" height="100%"/><g fill="#f2c94c" opacity="0.9"><rect x="48" y="48" width="120" height="18" rx="9"/><rect x="180" y="48" width="80" height="18" rx="9"/></g><text x="48" y="110" fill="#e9edf2" font-size="28" font-family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial">${esc(l1)}</text>${l2?`<text x="48" y="145" fill="#9aa1ab" font-size="18">${esc(l2)}</text>`:''}</svg>`;

  function sourceLabels(s){
    const map = {
      'PurdueSports.com':['Official','Purdue'],
      'BTN Purdue':['BTN','Purdue'],
      'Purdue Athletics YouTube':['YouTube','Official'],
      'Sports Illustrated CBB':['SI','CBB'],
      'CBS Sports CBB':['CBS','CBB'],
      'Yahoo CBB':['Yahoo','CBB'],
      'Rivals Purdue':['Rivals','Purdue'],
      'Gold and Black (Rivals)':['G&B','Purdue'],
      'Gold and Black':['G&B','Purdue'],
      'Journal & Courier':['J&C','Local']
    };
    return map[s] || ['News',''];
  }

  function sourceIcon(s=''){
    s = (s||'').toLowerCase();
    if (s.includes('btn')) return '🟦';
    if (s.includes('purdue athletics youtube') || s.includes('youtube')) return '▶️';
    if (s.includes('purdue')) return '🏅';
    if (s.includes('sports illustrated') || s === 'si') return '📰';
    if (s.includes('rivals') || s.includes('gold and black')) return '💬';
    if (s.includes('cbs')) return '📺';
    if (s.includes('yahoo')) return '🟣';
    return '🗞️';
  }

  function timeAgo(ts){
    try{
      const ms = typeof ts === 'number' ? ts : Number(ts);
      if (!ms) return '';
      const mins = (Date.now() - ms)/60000;
      if (mins < 1) return 'just now';
      if (mins < 60) return `${Math.round(mins)}m ago`;
      if (mins < 1440) return `${Math.round(mins/60)}h ago`;
      const dt = new Date(ms);
      return dt.toLocaleString([], {month:'short', day:'numeric'});
    }catch{return '';}
  }

  function metaLine(item){
    const bits = [];
    if (item.tier) bits.push(esc(item.tier));
    if (item.source) bits.push(esc(item.source));
    const when = timeAgo(item.ts);
    if (when) bits.push(when);
    return bits.join(' • ');
  }

  function render(items){
    const grid = byId('news-grid');
    const heroWrap = byId('news-hero');
    const heroMeta = byId('news-hero-meta');
    const newsStatus = byId('news-status');
    const vidsGrid = byId('videos-grid');
    const vidsStatus = byId('videos-status');

    if (!items || !items.length) {
      newsStatus.textContent = "No headlines.";
      newsStatus.hidden = false;
      vidsStatus.textContent = "No new videos.";
      vidsStatus.hidden = false;
      return;
    }

    items = items.slice().sort((a,b)=> (b.ts||0)-(a.ts||0));

    // HERO
    const heroIdx = Math.max(0, items.findIndex(i => (i.type||'article') !== 'video'));
    const hero = items[heroIdx] || items[0];
    const [l1,l2] = sourceLabels(hero.source||"Source");
    const heroBadge = sourceIcon(hero.source||'');
    heroWrap.innerHTML = `
      <a class="hero-img-wrap" href="${hero.link}" target="_blank" rel="noopener">
        <div class="hero-art">${posterSVG(l1,l2,true)}</div>
      </a>`;
    heroMeta.innerHTML = `
      <div class="pills">${hero.tier?pill(hero.tier):""}${hero.source?pill(hero.source):""}</div>
      <h3 class="card-title"><a href="${hero.link}" target="_blank" rel="noopener">${esc(hero.title||'Untitled')}</a></h3>
      <div class="meta-line">${esc(metaLine(hero))}</div>
    `;
    // badge overlay
    const b = document.createElement('div');
    b.className = 'card-badge';
    b.textContent = heroBadge;
    heroWrap.style.position = 'relative';
    heroWrap.appendChild(b);

    // GRID
    const rest = items.filter((_,i)=>i!==heroIdx);
    grid.innerHTML = rest.slice(0,15).map(i => {
      const [a,b] = sourceLabels(i.source||"");
      const isVid = (i.type||'article') === 'video';
      const badge = sourceIcon(i.source||'');
      return `
        <article class="card">
          <a class="card-img-wrap" href="${i.link}" target="_blank" rel="noopener" aria-label="${esc(i.title||'Open')}">
            <div class="card-badge" aria-hidden="true">${badge}</div>
            <div class="hero-art">${posterSVG(isVid?'Video':(a||'News'), b||'')}</div>
          </a>
          <div class="card-body">
            <div class="pills">${i.tier?pill(i.tier):""}${i.source?pill(i.source):""}</div>
            <a class="card-title" href="${i.link}" target="_blank" rel="noopener">${esc(i.title||'Untitled')}</a>
            <div class="meta-line">${esc(metaLine(i))}</div>
          </div>
        </article>`;
    }).join('');

    // VIDEOS
    const vids = items.filter(i => (i.type||'article') === 'video').slice(0,12);
    if (vids.length){
      vidsGrid.innerHTML = vids.map(v => {
        const [l1,l2] = sourceLabels(v.source||"");
        const badge = sourceIcon(v.source||'');
        return `
          <article class="card video-card">
            <a class="card-img-wrap" href="${v.link}" target="_blank" rel="noopener">
              <div class="card-badge" aria-hidden="true">${badge}</div>
              <div class="hero-art">${posterSVG('Video',l1||l2||'')}</div>
            </a>
            <div class="card-body">
              <div class="pills">${v.tier?pill(v.tier):""}${v.source?pill(v.source):""}</div>
              <a class="card-title" href="${v.link}" target="_blank" rel="noopener">${esc(v.title)}</a>
              <div class="meta-line">${esc(metaLine(v))}</div>
            </div>
          </article>`;
      }).join('');
      vidsStatus.hidden = true;
    } else {
      vidsStatus.textContent = "No new videos yet.";
      vidsStatus.hidden = false;
    }

    byId('updatedFooter').textContent = `Updated ${new Date().toLocaleString([], {hour:'2-digit', minute:'2-digit'})}`;
    byId('sourceCount').textContent = '';
  }

  // Seed-first render
  let seedItems = [];
  try {
    const tag = byId('seed-items');
    if (tag && tag.textContent.trim()) {
      const parsed = JSON.parse(tag.textContent);
      if (Array.isArray(parsed?.items)) seedItems = parsed.items;
    }
  } catch {}
  if (!seedItems.length) {
    seedItems = [
      {"title":"Purdue Announces 2025–26 Non-Conference Slate","link":"https://purduesports.com/","source":"PurdueSports.com","tier":"official","type":"article","ts":1762300800000}
    ];
  }
  render(seedItems);

  // Upgrade from items.json (RELATIVE path)
  (async function upgrade(){
    try{
      const res = await fetch(url('static/teams/purdue-mbb/items.json'), { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      if (data && Array.isArray(data.items) && data.items.length) render(data.items);
    }catch(e){/* silent */}
  })();

  // Hydrate external panels if present
  document.addEventListener('DOMContentLoaded', () => {
    if (window.PRO && typeof window.PRO.hydratePanels === 'function') {
      window.PRO.hydratePanels('./');
    }
  });
})();
