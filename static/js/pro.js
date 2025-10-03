(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);

  // 1) Hard-code GitHub Pages base for THIS repo.
  const PATH_BASE = '/sports-app-project/';
  const url = (p) => `${PATH_BASE}${p.replace(/^\//,'')}`;

  // 2) Optional image proxy (leave "" if not using Worker).
  const PROXY_BASE = ""; // e.g., "https://your-proxy.workers.dev"
  const PROXY_HOSTS = new Set([
    'img.si.com','si.com','gannett-cdn.com','jconline.com','s.yimg.com','yimg.com','yahoo.com',
    '247sports.imgix.net','247sports.com','rivalscdn.com','rivals.com','sportshqimages.cbsimg.net','cbssports.com',
    'vox-cdn.com','sbnation.com','espncdn.com','espn.com','apnews.com','nbcsports.com','i.ytimg.com','ytimg.com','youtube.com','purduesports.com'
  ]);

  // ------- Utils -------
  const escapeHTML = (s) => (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  function ftimeAgo(date){ try{const d=new Date(date);const diff=(Date.now()-d.getTime())/1000;if(diff<90)return'just now';const u=[['y',31536000],['mo',2592000],['d',86400],['h',3600],['m',60]];for(const [l,s] of u){const v=Math.floor(diff/s);if(v>=1)return`${v}${l} ago`;}return'just now';}catch(_){return''} }
  const etld1 = (host) => { if(!host) return ''; const p=host.toLowerCase().split('.').filter(Boolean); return p.length<=2?host.toLowerCase():p.slice(-2).join('.'); };
  function setDebug(msg){ const el=$('#debugMsg'); if(el) el.textContent=msg; console.log('[DEBUG]', msg); }
  function bannerError(text){
    let b=document.getElementById('fatalBanner');
    if(!b){ b=document.createElement('div'); b.id='fatalBanner';
      b.style.cssText='position:fixed;top:0;left:0;right:0;background:#200;color:#fff;padding:8px 12px;z-index:9999;font:600 14px system-ui';
      document.body.appendChild(b);
    }
    b.textContent = text;
  }

  // ------- Images -------
  function ytId(urlStr){ try{const u=new URL(urlStr); if(u.hostname.includes('youtu.be')) return u.pathname.slice(1); if(u.searchParams.get('v')) return u.searchParams.get('v'); const m=/\/embed\/([^?]+)/.exec(u.pathname); return m?m[1]:null;}catch(_){return null} }
  const ytThumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
  function isLikelyBadImage(src){ if(!src) return true; const s=src.toLowerCase();
    if(/(sprite|logo|placeholder|default|blank|spacer)\.(png|svg|gif)$/.test(s)) return true;
    if(!/\.(jpg|jpeg|png|webp)(\?|$)/.test(s)) return true; return false; }
  function proxify(src){ if(!PROXY_BASE) return src; try{ const h=etld1(new URL(src).host.toLowerCase()); if(PROXY_HOSTS.has(h)) return `${PROXY_BASE}/?u=${encodeURIComponent(src)}`; return src; }catch{ return src; } }
  function selectImageForItem(item){ const id=ytId(item.link||''); if(id) return ytThumb(id); const c=item.image||''; if(!c||isLikelyBadImage(c)) return ''; return proxify(c); }

  // ------- UI helpers -------
  function initialsFrom(str=''){ const parts=(str||'').trim().split(/\s+/); const a=(parts[0]||'')[0]||''; const b=(parts[1]||'')[0]||''; return (a+b).toUpperCase() || '•'; }
  function fallbackNode(aspect,label){ const div=document.createElement('div'); div.className=aspect==='16x9'?'fallback-16x9':'fallback-4x3'; const inner=document.createElement('div'); inner.className='fallback-badge'; inner.textContent=initialsFrom(label); div.appendChild(inner); return div; }
  function attachImgFallbacks(ctx=document){ ctx.querySelectorAll('img[data-aspect]').forEach(img=>{ const a=img.getAttribute('data-aspect'); const l=img.getAttribute('data-label')||''; img.addEventListener('error',()=>{ img.replaceWith(fallbackNode(a,l)); },{once:true}); }); }
  function badge(tag){ const t=(tag||'').toLowerCase(); if(t.includes('official'))return`<span class="pill">official</span>`; if(t.includes('insider'))return`<span class="pill">insiders</span>`; if(t.includes('national'))return`<span class="pill">national</span>`; return t?`<span class="pill">${escapeHTML(t)}</span>`:''; }

  // ------- Dual-path fetch (with explicit errors) -------
  async function fetchJSON(relPath){
    const primary = url(relPath);              // /sports-app-project/static/...
    const fallback = `/${relPath.replace(/^\//,'')}`; // /static/... (root) if someone moved files
    const tryFetch = async (href) => {
      try{ const r=await fetch(href,{cache:'no-cache'}); if(!r.ok) return {ok:false,status:r.status,href}; return {ok:true,json:await r.json(),href}; }
      catch(e){ return {ok:false,status:'ERR',href}; }
    };
    let res = await tryFetch(primary);
    if(!res.ok){ setDebug(`${relPath} → ${res.status} @ ${primary}`); res = await tryFetch(fallback); }
    if(!res.ok){ setDebug(`${relPath} → ${res.status} @ ${fallback}`); bannerError(`Data missing: ${relPath} (see footer)`); return null; }
    return res.json;
  }

  // ------- Panels -------
  async function loadRankings(){
    const w = await fetchJSON('static/widgets.json');
    if(!w) return;
    $('#apRank').textContent = w.ap_rank ? `#${w.ap_rank}` : '—';
    $('#kpRank').textContent = w.kenpom_rank ? `#${w.kenpom_rank}` : '—';
    if (w.ap_url) $('#apLink').href = w.ap_url;
    if (w.kenpom_url) $('#kpLink').href = w.kenpom_url;
    if (w.updated_at){ const ts=new Date(w.updated_at);
      $('#rankUpdated').textContent = `as of ${ts.toLocaleString([], {month:'short', day:'numeric'})}`; }
  }

  function initials(name='?'){
    const clean = name.replace(/^[@vs]\s*/,'').replace(/\(.*?\)/g,'');
    const parts = clean.trim().split(/\s+/);
    const letters = (parts[0][0]||'').toUpperCase() + ((parts[1]||'')[0]||'').toUpperCase();
    return letters || '•';
  }
  function siteClass(site){ const s=(site||'').toLowerCase(); if(s.startsWith('home'))return'site-home'; if(s.startsWith('away'))return'site-away'; if(s.startsWith('neutral'))return'site-neutral'; return''; }

  async function loadSchedule(){
    const sched = await fetchJSON('static/schedule.json'); if(!sched) return;
    const list=$('#scheduleList');
    list.innerHTML = sched.slice(0,6).map(g=>{
      const dt=new Date(g.utc||g.date);
      const time=dt.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
      const day=dt.toLocaleDateString([], {year:'numeric', month:'2-digit', day:'2-digit'});
      const site=g.site||'TBD'; const tz=Intl.DateTimeFormat().resolvedOptions().timeZone.split('/').pop();
      return `<a class="game ${siteClass(site)}" href="${g.espn_url||'#'}" target="_blank" rel="noopener">
        <div class="g-top"><span>${day}</span><span>${time} <small>${tz}</small></span></div>
        <div class="g-title"><span class="logo-pill">${initials(g.opp||'')}</span> ${escapeHTML(g.opp||'Opponent')} <span class="pill">${site}</span></div>
      </a>`;
    }).join('');
  }

  function renderHero(lead){
    const hero=$('#hero'); hero.classList.remove('skeleton');
    const src = selectImageForItem(lead);
    const label = lead.source || lead.title || '';
    const media = src
      ? `<img class="hero-img" data-aspect="16x9" data-label="${escapeHTML(label)}" src="${src}" alt="" loading="eager" fetchpriority="high" decoding="async" crossorigin="anonymous">`
      : `<div class="fallback-16x9"><div class="fallback-badge">${initialsFrom(label)}</div></div>`;
    hero.innerHTML = `
      <a href="${lead.link}" target="_blank" rel="noopener" class="hero-img-wrap">${media}</a>
      <div class="hero-meta">
        <div class="pills">
          ${badge(lead.tier||lead.tag||'')}
          <span class="pill">${escapeHTML(lead.source||'')}</span>
          <span class="pill">${ftimeAgo(lead.date||lead.published||new Date().toISOString())}</span>
        </div>
        <h3 class="hero-title"><a href="${lead.link}" target="_blank" rel="noopener">${escapeHTML(lead.title||'')}</a></h3>
        <div class="hero-sub">${escapeHTML(lead.summary||'')}</div>
      </div>`;
    attachImgFallbacks(hero);
  }

  const renderCard = (i) => {
    const when=ftimeAgo(i.date||i.published||new Date().toISOString());
    const src = selectImageForItem(i);
    const label=i.source||i.title||'';
    const media = src
      ? `<img class="card-img" data-aspect="4x3" data-label="${escapeHTML(label)}" src="${src}" alt="" loading="lazy" decoding="async" crossorigin="anonymous">`
      : `<div class="fallback-4x3"><div class="fallback-badge">${initialsFrom(label)}</div></div>`;
    return `<article class="card">
      <a class="card-img-wrap" href="${i.link}" target="_blank" rel="noopener">${media}</a>
      <div class="card-body">
        <div class="card-meta">${badge(i.tier||i.tag)} <span>${escapeHTML(i.source||'')}</span> • <span>${when}</span></div>
        <a class="card-title" href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title||'')}</a>
      </div>
    </article>`;
  };

  async function loadItems(){
    const data = await fetchJSON('static/teams/purdue-mbb/items.json'); if(!data) return;
    const items = (data.items || data || []); const list = items.slice(0,18);

    $('#tickerTrack').innerHTML = list.slice(0,12)
      .map(i => `<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`).join('');

    if (list.length){
      renderHero(list[0]);
      const grid = $('#headlines');
      grid.innerHTML = list.slice(1).map(renderCard).join('');
      attachImgFallbacks(grid);
    }

    $('#updatedFooter').textContent = `Updated ${new Date().toLocaleString([], {hour:'2-digit', minute:'2-digit'})}`;
    $('#sourceCount').textContent   = data.sources ? `• ${data.sources.length} sources` : '';
  }

  async function loadInsiders(){
    const data = await fetchJSON('static/insiders.json'); if(!data) return;
    const el=$('#insiderList');
    el.innerHTML=data.map(o=>{
      const pay=o.pay?'<span class="badge-pay">$</span>':'';
      const sub=o.latest_headline?`<div class="link-sub">${escapeHTML(o.latest_headline)}</div>`:'';
      const meta=o.updated_at?`<span>${ftimeAgo(o.updated_at)}</span>`:'';
      return `<a class="link-card" href="${o.latest_url||o.url}" target="_blank" rel="noopener">
        <div class="link-logo">📰</div>
        <div class="link-body"><div class="link-title">${escapeHTML(o.name)}</div>${sub}</div>
        <div class="link-meta">${o.type}${pay}${meta?` • ${meta}`:''}</div>
      </a>`;
    }).join('');
  }

  async function init(){
    await Promise.all([loadRankings(), loadSchedule(), loadItems(), loadInsiders()]);
  }
  document.addEventListener('DOMContentLoaded', init);
})();