(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);

  // Base path for GH Pages (e.g., /sports-app-project/)
  const PATH_BASE = (function(){
    const parts = location.pathname.split('/').filter(Boolean);
    return parts.length ? `/${parts[0]}/` : '/';
  })();
  const url = (p) => `${PATH_BASE}${p.replace(/^\//,'')}`;

  /* ========== Utils ========== */
  const escapeHTML = (s) => (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  function ftimeAgo(date){ try{const d=new Date(date);const diff=(Date.now()-d.getTime())/1000;if(diff<90)return'just now';const u=[['y',31536000],['mo',2592000],['d',86400],['h',3600],['m',60]];for(const [l,s] of u){const v=Math.floor(diff/s);if(v>=1)return`${v}${l} ago`;}return'just now';}catch(_){return''} }
  const debug = (m) => { const el=$('#debugMsg'); if(el) el.textContent=m; console.log('[DEBUG]', m); };

  /* ========== Image selection & fallback (no inline JS) ========== */
  const KNOWN_IMG_HOSTS = [
    /apnews\.com/i, /gannett-cdn\.com/i, /si\.com|img\.si\.com/i, /yimg\.com/i,
    /247sports\.com|247sports\.imgix\.net/i, /rivals\.com/i, /cbssports\.com|sportshqimages\.cbsimg\.net/i,
    /nbcsports/i, /espn\.com|espncdn\.com/i, /purduesports\.com/i, /sbnation\.com|vox-cdn\.com/i,
    /youtube\.com|ytimg\.com/i
  ];
  const isKnownImgHost = (h) => KNOWN_IMG_HOSTS.some(rx => rx.test(h||''));

  function eTLD1(host){
    if(!host) return '';
    const parts = host.toLowerCase().split('.').filter(Boolean);
    if (parts.length <= 2) return host.toLowerCase();
    return parts.slice(-2).join('.');
  }

  function isLikelyBadImage(src){
    if(!src) return true;
    const s = src.toLowerCase();
    if (/(sprite|logo|placeholder|default|blank|spacer)\.(png|svg|gif)$/.test(s)) return true;
    if (!/\.(jpg|jpeg|png|webp)(\?|$)/.test(s)) return true;
    try{
      const u = new URL(src);
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
    const parts=(str||'').trim().split(/\s+/);
    const a=(parts[0]||'')[0]||''; const b=(parts[1]||'')[0]||'';
    return (a+b).toUpperCase() || '•';
  }

  function fallbackNode(aspect,label){
    const div = document.createElement('div');
    div.className = aspect==='16x9' ? 'fallback-16x9' : 'fallback-4x3';
    const inner = document.createElement('div');
    inner.className = 'fallback-badge';
    inner.textContent = initialsFrom(label);
    div.appendChild(inner);
    return div;
  }

  function attachImgFallbacks(ctx=document){
    ctx.querySelectorAll('img[data-aspect]').forEach(img => {
      const aspect = img.getAttribute('data-aspect');
      const label  = img.getAttribute('data-label') || '';
      img.addEventListener('error', () => {
        const node = fallbackNode(aspect, label);
        img.replaceWith(node);
      }, {once:true});
    });
  }

  function selectImageForItem(item){
    // Prefer YouTube thumbnail if link is YT
    const id = ytId(item.link||'');
    if (id) return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;

    const candidate = item.image || '';
    if (!candidate || isLikelyBadImage(candidate)) return '';

    // Host match/whitelist
    try{
      const imgHost = new URL(candidate).host;
      const linkHost= new URL(item.link||'', location.href).host;
      if (eTLD1(imgHost) === eTLD1(linkHost) || isKnownImgHost(imgHost)) {
        return candidate;
      }
      // Reject cross-site mismatches (prevents random logos)
      return '';
    }catch(_){
      return '';
    }
  }

  /* ========== UI helpers ========== */
  function badge(tag){
    const t=(tag||'').toLowerCase();
    if (t.includes('official')) return `<span class="pill">official</span>`;
    if (t.includes('insider'))  return `<span class="pill">insider</span>`;
    if (t.includes('national')) return `<span class="pill">national</span>`;
    return t ? `<span class="pill">${escapeHTML(t)}</span>` : '';
  }

  /* ========== Data loaders ========== */
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

  /* ========== Headlines ========== */
  function renderHero(lead){
    const hero = $('#hero');
    hero.classList.remove('skeleton');

    const src = selectImageForItem(lead);
    const label = lead.source || lead.title || '';

    const media = src
      ? `<img class="hero-img" data-aspect="16x9" data-label="${escapeHTML(label)}"
               src="${src}" alt="" loading="eager" decoding="async"
               referrerpolicy="no-referrer" crossorigin="anonymous">`
      : `<div class="fallback-16x9"><div class="fallback-badge">${initialsFrom(label)}</div></div>`;

    hero.innerHTML = `
      <a href="${lead.link}" target="_blank" rel="noopener" class="hero-img-wrap">
        ${media}
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
    attachImgFallbacks(hero);
  }

  const renderCard = (i) => {
    const when  = ftimeAgo(i.date||i.published||new Date().toISOString());
    const src   = selectImageForItem(i);
    const label = i.source || i.title || '';
    const media = src
      ? `<img class="card-img" data-aspect="4x3" data-label="${escapeHTML(label)}"
               src="${src}" alt="" loading="lazy" decoding="async"
               referrerpolicy="no-referrer" crossorigin="anonymous">`
      : `<div class="fallback-4x3"><div class="fallback-badge">${initialsFrom(label)}</div></div>`;
    return `
      <article class="card">
        <a class="card-img-wrap" href="${i.link}" target="_blank" rel="noopener">
          ${media}
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
    }catch(e){ debug('items: '+e.message); }
  }

  /* ========== Videos ========== */
  function ytThumb(id){ return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`; }

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

      const grid = $('#videoGrid');
      grid.innerHTML = videos.map(v => {
        const id = ytId(v.link||'');
        const src = id ? ytThumb(id) : selectImageForItem(v);
        const label = v.source || v.title || '';
        const media = src
          ? `<img data-aspect="16x9" data-label="${escapeHTML(label)}" src="${src}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" crossorigin="anonymous">`
          : `<div class="fallback-16x9"><div class="fallback-badge">${initialsFrom(label)}</div></div>`;
        return `<article class="video">
          <a class="video-thumb" href="${v.link}" data-yt="${id||''}">
            ${media}
            ${v.duration ? `<span class="video-duration">${v.duration}</span>`:''}
          </a>
          <div class="video-body">
            <div class="video-title"><a href="${v.link}" data-yt="${id||''}">${escapeHTML(v.title||'')}</a></div>
            <div class="video-meta">${escapeHTML(v.source||'')} • ${ftimeAgo(v.date||v.published||new Date().toISOString())}</div>
          </div>
        </article>`;
      }).join('');
      attachImgFallbacks(grid);
    }catch(e){ debug('videos: '+e.message); }
  }

  /* ========== Insiders ========== */
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

  /* ========== Init ========== */
  async function init(){
    setupModal();
    await Promise.all([loadRankings(), loadSchedule(), loadItems(), loadVideos(), loadInsiders()]);
  }
  document.addEventListener('DOMContentLoaded', init);
})();