(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);

  // Base path for GH Pages (e.g., /sports-app-project/)
  const PATH_BASE = (function(){
    const parts = location.pathname.split('/').filter(Boolean);
    return parts.length ? `/${parts[0]}/` : '/';
  })();
  const url = (p) => `${PATH_BASE}${p.replace(/^\//,'')}`;

  /* ---------- Utilities ---------- */
  function escapeHTML(s){ return (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }
  function ftimeAgo(date){
    try{
      const d=new Date(date); const diff=(Date.now()-d.getTime())/1000;
      if(diff<90) return 'just now';
      const units=[['y',31536000],['mo',2592000],['d',86400],['h',3600],['m',60]];
      for(const [l,s] of units){ const v=Math.floor(diff/s); if(v>=1) return `${v}${l} ago`; }
      return 'just now';
    }catch(e){return''}
  }
  function debug(msg){ const el=$('#debugMsg'); if(el) el.textContent=msg; console.log('[DEBUG]', msg); }

  /* ---------- IMAGE ACCURACY HEURISTICS ---------- */
  // Some feeds provide logos/placeholders or hotlink-protected images.
  // Heuristics:
  //  - Prefer YouTube thumbnails when link is YT.
  //  - Drop likely-bad filenames (logo, sprite, default, placeholder, blank).
  //  - If image host is a known CDN pattern but filename tiny (<= 20 chars) w/out extension, drop.
  //  - Always add referrerpolicy="no-referrer" to reduce 403 blocks.
  function isLikelyBadImage(src){
    if(!src) return true;
    const s = src.toLowerCase();
    if (/(sprite|logo|placeholder|default|blank|spacer)\./.test(s)) return true;
    if (!/\.(jpg|jpeg|png|webp|gif)(\?|$)/.test(s)) return true;
    try{
      const u = new URL(src);
      // Filenames like ".../img?id=123" are often trackers; let them pass only if host matches link later.
      const name = u.pathname.split('/').pop() || '';
      if (name.length <= 4) return true;
    }catch(_){}
    return false;
  }
  function ytId(urlStr){
    try{
      const u = new URL(urlStr);
      if (u.hostname.includes('youtu.be')) return u.pathname.slice(1);
      if (u.searchParams.get('v')) return u.searchParams.get('v');
      const m = /\/embed\/([^?]+)/.exec(u.pathname);
      if (m) return m[1];
      return null;
    }catch(_){ return null }
  }
  function initialsFrom(str=''){
    const parts=(str||'').split(/\s+/);
    const a=(parts[0]||'')[0]||''; const b=(parts[1]||'')[0]||'';
    return (a+b).toUpperCase() || '•';
  }
  function buildFallback(aspect,label){
    const cls = aspect==='16x9' ? 'fallback-16x9' : 'fallback-4x3';
    return `<div class="${cls}"><div class="fallback-badge">${escapeHTML(initialsFrom(label))}</div></div>`;
  }
  function safeImgTag(src, aspect, label){
    if (isLikelyBadImage(src)) return buildFallback(aspect, label);
    return `<img
      src="${src}"
      alt=""
      class="${aspect==='16x9'?'hero-img':'card-img'}"
      loading="${aspect==='16x9'?'eager':'lazy'}"
      decoding="async"
      referrerpolicy="no-referrer"
      crossorigin="anonymous"
      onerror="this.replaceWith((${buildFallback}).call(null,'${aspect}','${escapeHTML(label)}'))"
    >`;
  }

  /* ---------- UI helpers ---------- */
  function badge(tag){
    const t=(tag||'').toLowerCase();
    if (t.includes('official')) return `<span class="pill">official</span>`;
    if (t.includes('insider'))  return `<span class="pill">insider</span>`;
    if (t.includes('national')) return `<span class="pill">national</span>`;
    return t ? `<span class="pill">${escapeHTML(t)}</span>` : '';
  }

  /* ---------- Data loaders ---------- */
  async function getTeam(){
    try{
      const r = await fetch(url('static/team.json'), {cache:'no-cache'});
      if (r.ok){
        const j = await r.json();
        return j.slug || j.team?.slug || j.id || window.__TEAM_SLUG || 'purdue-mbb';
      }
    }catch(_){}
    return window.__TEAM_SLUG || 'purdue-mbb';
  }

  async function loadRankings(){
    try{
      const r = await fetch(url('static/widgets.json'), {cache:'no-cache'});
      if (!r.ok) throw new Error(`widgets.json ${r.status}`);
      const w = await r.json();
      $('#apRank').textContent = w.ap_rank ? `#${w.ap_rank}` : '—';
      $('#kpRank').textContent = w.kenpom_rank ? `#${w.kenpom_rank}` : '—';
      if (w.ap_url) $('#apLink').href = w.ap_url;
      if (w.kenpom_url) $('#kpLink').href = w.kenpom_url;
      if (w.updated_at){
        const ts = new Date(w.updated_at);
        $('#rankUpdated').textContent = `as of ${ts.toLocaleString([], {month:'short', day:'numeric'})}`;
      }
    }catch(e){ debug('rankings: '+e.message); }
  }

  function initials(name='?'){
    const clean = name.replace(/^[@vs]\s*/,'').replace(/\(.*?\)/g,'');
    const parts = clean.trim().split(/\s+/);
    const letters = (parts[0][0]||'').toUpperCase() + ((parts[1]||'')[0]||'').toUpperCase();
    return letters || '•';
  }
  function siteClass(site){
    const s=(site||'').toLowerCase();
    if (s.startsWith('home')) return 'site-home';
    if (s.startsWith('away')) return 'site-away';
    if (s.startsWith('neutral')) return 'site-neutral';
    return '';
  }
  async function loadSchedule(){
    try{
      const r = await fetch(url('static/schedule.json'), {cache:'no-cache'});
      if (!r.ok) throw new Error(`schedule.json ${r.status}`);
      const sched = await r.json();
      const list  = $('#scheduleList');
      list.innerHTML = sched.slice(0,6).map(g => {
        const dt   = new Date(g.utc || g.date);
        const time = dt.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
        const day  = dt.toLocaleDateString([], {year:'numeric', month:'2-digit', day:'2-digit'});
        const site = g.site || 'TBD';
        const tz   = Intl.DateTimeFormat().resolvedOptions().timeZone.split('/').pop();
        return `<a class="game ${siteClass(site)}" href="${g.espn_url||'#'}" target="_blank" rel="noopener">
          <div class="g-top"><span>${day}</span><span>${time} <small>${tz}</small></span></div>
          <div class="g-title"><span class="logo-pill">${initials(g.opp||'')}</span> ${escapeHTML(g.opp||'Opponent')} <span class="pill">${site}</span></div>
        </a>`;
      }).join('');
    }catch(e){ debug('schedule: '+e.message); }
  }

  /* ---------- Headlines ---------- */
  function pickImageForItem(item){
    // Prefer YouTube derived thumbnail if link is YT
    const id = ytId(item.link||'');
    if (id) return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
    // Otherwise use provided image if not likely bad
    if (item.image && !isLikelyBadImage(item.image)) return item.image;
    return ''; // will trigger fallback
  }

  function renderHero(lead){
    const hero = $('#hero');
    hero.classList.remove('skeleton');
    const src = pickImageForItem(lead);
    const sourceLabel = lead.source || lead.title || '';
    hero.innerHTML = `
      <a href="${lead.link}" target="_blank" rel="noopener" class="hero-img-wrap">
        ${ src ? safeImgTag(src,'16x9',sourceLabel) : buildFallback('16x9', sourceLabel) }
      </a>
      <div class="hero-meta">
        <div class="pills">
          ${badge(lead.tier || lead.tag || '')}
          <span class="pill">${escapeHTML(lead.source||'')}</span>
          <span class="pill">${ftimeAgo(lead.date||lead.published||new Date().toISOString())}</span>
        </div>
        <h3 class="hero-title"><a href="${lead.link}" target="_blank" rel="noopener">${escapeHTML(lead.title||'')}</a></h3>
        <div class="hero-sub">${escapeHTML(lead.summary||'')}</div>
      </div>
    `;
  }

  const renderCard = (i) => {
    const when = ftimeAgo(i.date||i.published||new Date().toISOString());
    const src  = pickImageForItem(i);
    const label = i.source || i.title || '';
    return `
      <article class="card">
        <a class="card-img-wrap" href="${i.link}" target="_blank" rel="noopener">
          ${ src ? safeImgTag(src,'4x3',label) : buildFallback('4x3',label) }
        </a>
        <div class="card-body">
          <div class="card-meta">${badge(i.tier||i.tag)} <span>${escapeHTML(i.source||'')}</span> • <span>${when}</span></div>
          <a class="card-title" href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title||'')}</a>
        </div>
      </article>`;
  };

  async function loadItems(){
    try{
      const slug = await getTeam();
      const r = await fetch(url(`static/teams/${slug}/items.json`), {cache:'no-cache'});
      if (!r.ok) throw new Error(`items.json for ${slug} -> ${r.status}`);
      const data  = await r.json();
      const items = (data.items || data || []);
      const list  = items.slice(0,18);

      // Ticker
      $('#tickerTrack').innerHTML = list.slice(0,12)
        .map(i => `<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`)
        .join('');

      // Hero + cards
      if (list.length){
        renderHero(list[0]);
        $('#headlines').innerHTML = list.slice(1).map(renderCard).join('');
      }

      // Footer freshness
      $('#updatedFooter').textContent = `Updated ${new Date().toLocaleString([], {hour:'2-digit', minute:'2-digit'})}`;
      $('#sourceCount').textContent   = data.sources ? `• ${data.sources.length} sources` : '';
    }catch(e){ debug('items: '+e.message); }
  }

  /* ---------- Videos ---------- */
  function setupModal(){
    const modal = $('#videoModal'); if (!modal) return;
    modal.addEventListener('click', (e) => { if (e.target.hasAttribute('data-close')) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-yt]'); if(!a) return;
      const id = a.getAttribute('data-yt'); if(!id) return;
      e.preventDefault(); openModal(id);
    });
  }
  function openModal(id){
    $('#modalPlayer').innerHTML = `<iframe width="100%" height="100%" src="https://www.youtube.com/embed/${id}?autoplay=1" title="YouTube video" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
    $('#videoModal').setAttribute('aria-hidden','false');
  }
  function closeModal(){
    $('#modalPlayer').innerHTML = '';
    $('#videoModal').setAttribute('aria-hidden','true');
  }
  async function loadVideos(){
    try{
      const slug = await getTeam();
      const r = await fetch(url(`static/teams/${slug}/items.json`), {cache:'no-cache'});
      if (!r.ok) throw new Error(`videos: items.json ${r.status}`);
      const data = await r.json();
      const videos = (data.items || data || []).filter(i => (i.type||'').includes('video') || /youtube\.com|youtu\.be/.test(i.link||'')).slice(0,8);
      const grid = document.getElementById('videoGrid');
      grid.innerHTML = videos.map(v => {
        const id = ytId(v.link||'');
        const thumb = id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : pickImageForItem(v);
        const label = v.source || v.title || '';
        return `<article class="video">
          <a class="video-thumb" href="${v.link}" data-yt="${id||''}">
            ${ thumb ? `<img src="${thumb}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" crossorigin="anonymous" onerror="this.replaceWith((${buildFallback}).call(null,'16x9','${escapeHTML(label)}'))">` : buildFallback('16x9', label) }
            ${v.duration ? `<span class="video-duration">${v.duration}</span>`:''}
          </a>
          <div class="video-body">
            <div class="video-title"><a href="${v.link}" data-yt="${id||''}">${escapeHTML(v.title||'')}</a></div>
            <div class="video-meta">${escapeHTML(v.source||'')} • ${ftimeAgo(v.date||v.published||new Date().toISOString())}</div>
          </div>
        </article>`;
      }).join('');
    }catch(e){ debug('videos: '+e.message); }
  }

  /* ---------- Insiders (unchanged content) ---------- */
  async function loadInsiders(){
    try{
      const r = await fetch(url('static/insiders.json'), {cache:'no-cache'});
      if (!r.ok) throw new Error(`insiders.json ${r.status}`);
      const data = await r.json();
      const el = $('#insiderList');
      el.innerHTML = data.map(o => {
        const pay = o.pay ? '<span class="badge-pay">$</span>' : '';
        const sub = o.latest_headline ? `<div class="link-sub">${escapeHTML(o.latest_headline)}</div>` : '';
        const meta = o.updated_at ? `<span>${ftimeAgo(o.updated_at)}</span>` : '';
        return `<a class="link-card" href="${o.latest_url || o.url}" target="_blank" rel="noopener">
          <div class="link-logo">📰</div>
          <div class="link-body"><div class="link-title">${escapeHTML(o.name)}</div>${sub}</div>
          <div class="link-meta">${o.type}${pay}${meta?` • ${meta}`:''}</div>
        </a>`;
      }).join('');
    }catch(e){ debug('insiders: '+e.message); }
  }

  /* ---------- Init ---------- */
  async function init(){
    setupModal();
    await Promise.all([loadRankings(), loadSchedule(), loadItems(), loadVideos(), loadInsiders()]);
  }
  document.addEventListener('DOMContentLoaded', init);
})();
