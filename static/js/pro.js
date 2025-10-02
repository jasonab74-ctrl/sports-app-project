
(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);

  // Compute base path for GH Pages (e.g., /sports-app-project/)
  const PATH_BASE = (function(){
    const parts = location.pathname.split('/').filter(Boolean);
    return parts.length ? `/${parts[0]}/` : '/';
  })();
  const url = (p) => `${PATH_BASE}${p.replace(/^\//,'')}`;

  // Mobile drawer
  function mountDrawer(){
    const toggle = $('#navToggle');
    const drawer = $('#drawer');
    if (!toggle || !drawer) return;
    const open = () => drawer.setAttribute('aria-hidden', 'false');
    const close = () => drawer.setAttribute('aria-hidden', 'true');
    toggle.addEventListener('click', () => {
      const isOpen = drawer.getAttribute('aria-hidden') === 'false';
      isOpen ? close() : open();
      toggle.setAttribute('aria-expanded', String(!isOpen));
    });
    drawer.addEventListener('click', (e) => {
      if (e.target.hasAttribute('data-close')) close();
    });
  }

  // Team slug
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

  function ftimeAgo(date){
    try{
      const d = new Date(date);
      const diff = (Date.now()-d.getTime())/1000;
      if (diff < 90) return 'just now';
      const units = [['y',31536000],['mo',2592000],['d',86400],['h',3600],['m',60]];
      for (const [label, secs] of units){
        const v = Math.floor(diff/secs);
        if (v >= 1) return `${v}${label} ago`;
      }
      return 'just now';
    }catch(e){ return ''}
  }

  function badge(tag){
    const t = (tag||'').toLowerCase();
    if (t.includes('official')) return `<span class="pill">official</span>`;
    if (t.includes('insider')) return `<span class="pill">insider</span>`;
    if (t.includes('national')) return `<span class="pill">national</span>`;
    return t ? `<span class="pill">${escapeHTML(t)}</span>` : '';
  }
  function escapeHTML(s){ return (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }

  function onImgError(img){
    if (!img) return;
    const wrap = img.closest('.hero-img-wrap, .card-img-wrap, .video-thumb');
    if (wrap) {
      img.remove();
      wrap.style.background = '#17181d';
      wrap.style.minHeight = '120px';
    }
  }

  function renderHero(lead){
    const hero = $('#hero');
    hero.classList.remove('skeleton');
    hero.innerHTML = `
      <a href="${lead.link}" target="_blank" rel="noopener" class="hero-img-wrap">
        ${lead.image ? `<img class="hero-img" src="${lead.image}" alt="" loading="eager" decoding="async" onerror="(${onImgError})(this)"/>` : ''}
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
    const img = i.image || '';
    return `
      <article class="card">
        <a class="card-img-wrap" href="${i.link}" target="_blank" rel="noopener">
          ${img ? `<img class="card-img" src="${img}" alt="" loading="lazy" decoding="async" onerror="(${onImgError})(this)">` : ''}
        </a>
        <div class="card-body">
          <div class="card-meta">${badge(i.tier||i.tag)} <span>${escapeHTML(i.source||'')}</span> • <span>${when}</span></div>
          <a class="card-title" href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title||'')}</a>
        </div>
      </article>`;
  };

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
    }catch(e){
      debug('rankings: ' + e.message);
    }
  }

  function initials(name='?'){
    const clean = name.replace(/^[@vs]\s*/,'').replace(/\(.*?\)/g,'');
    const parts = clean.trim().split(/\s+/);
    const letters = (parts[0][0]||'').toUpperCase() + ((parts[1]||'')[0]||'').toUpperCase();
    return letters || '•';
  }
  function siteClass(site){
    const s = (site||'').toLowerCase();
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
      const list = $('#scheduleList');
      list.innerHTML = sched.slice(0,6).map(g => {
        const dt = new Date(g.utc || g.date);
        const time = dt.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
        const day = dt.toLocaleDateString([], {year:'numeric', month:'2-digit', day:'2-digit'});
        const site = g.site || 'TBD';
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone.split('/').pop();
        return `<a class="game ${siteClass(site)}" href="${g.espn_url||'#'}" target="_blank" rel="noopener">
          <div class="g-top"><span>${day}</span><span>${time} <small>${tz}</small></span></div>
          <div class="g-title"><span class="logo-pill">${initials(g.opp||'')}</span> ${escapeHTML(g.opp||'Opponent')} <span class="tag">${site}</span></div>
        </a>`;
      }).join('');
    }catch(e){
      debug('schedule: ' + e.message);
    }
  }

  function loadInsiders(){
    const insiders = [
      {name:'Hammer & Rails', url:'https://www.hammerandrails.com/', type:'insiders'},
      {name:'Gold and Black', url:'https://purdue.rivals.com/', type:'insiders', pay:true},
      {name:'247Sports Purdue', url:'https://247sports.com/college/purdue/', type:'insiders', pay:true},
      {name:'Journal & Courier', url:'https://www.jconline.com/sports/purdue/', type:'insiders'},
      {name:'SB Nation — Purdue', url:'https://www.sbnation.com/college-basketball/teams/purdue-boilermakers', type:'insiders'},
      {name:'Team page', url:'https://purduesports.com/sports/mens-basketball', type:'official'}
    ];
    const el = $('#insiderList');
    el.innerHTML = insiders.map(o => {
      return `<a class="link-card" href="${o.url}" target="_blank" rel="noopener">
        <div class="link-logo">📰</div>
        <div class="link-title">${escapeHTML(o.name)}</div>
        <div class="link-meta">${o.type}${o.pay?'<span class="badge-pay tag">$</span>':''}</div>
      </a>`;
    }).join('');
  }

  async function loadItems(){
    try{
      const slug = await getTeam();
      const r = await fetch(url(`static/teams/${slug}/items.json`), {cache:'no-cache'});
      if (!r.ok) throw new Error(`items.json for ${slug} -> ${r.status}`);
      const data = await r.json();
      const items = (data.items || data || []).slice(0, 18);

      const tt = $('#tickerTrack');
      tt.innerHTML = items.slice(0,12).map(i => `<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`).join('');

      if(items.length){
        renderHero(items[0]);
        $('#headlines').innerHTML = items.slice(1).map(renderCard).join('');
      }
      $('#updatedFooter').textContent = `Updated ${new Date().toLocaleString([], {hour:'2-digit', minute:'2-digit'})}`;
      $('#sourceCount').textContent = data.sources ? `• ${data.sources.length} sources` : '';
    }catch(e){
      debug('items: ' + e.message);
    }
  }

  function setupModal(){
    const modal = $('#videoModal');
    if (!modal) return;
    modal.addEventListener('click', (e) => {
      if (e.target.hasAttribute('data-close')) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if(e.key === 'Escape') closeModal();
    });
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-yt]');
      if(!a) return;
      const id = a.getAttribute('data-yt');
      if(id){ e.preventDefault(); openModal(id); }
    });
  }
  function openModal(id){
    const modal = $('#videoModal');
    $('#modalPlayer').innerHTML = `<iframe width="100%" height="100%" src="https://www.youtube.com/embed/${id}?autoplay=1" title="YouTube video" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
    modal.setAttribute('aria-hidden','false');
  }
  function closeModal(){
    const modal = $('#videoModal');
    $('#modalPlayer').innerHTML = '';
    modal.setAttribute('aria-hidden','true');
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
        const thumb = v.image || (id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : '');
        return `<article class="video">
          <a class="video-thumb" href="${v.link}" data-yt="${id||''}">
            ${thumb ? `<img src="${thumb}" alt="" loading="lazy" decoding="async" onerror="(${onImgError})(this)">` : ''}
            ${v.duration ? `<span class="video-duration">${v.duration}</span>`:''}
          </a>
          <div class="video-body">
            <div class="video-title"><a href="${v.link}" data-yt="${id||''}">${escapeHTML(v.title||'')}</a></div>
            <div class="video-meta">${escapeHTML(v.source||'')} • ${ftimeAgo(v.date||v.published||new Date().toISOString())}</div>
          </div>
        </article>`;
      }).join('');
    }catch(e){
      debug('videos: ' + e.message);
    }
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

  function debug(msg){
    const el = $('#debugMsg'); if (el) el.textContent = msg;
    console.log('[DEBUG]', msg);
  }

  async function init(){
    mountDrawer();
    setupModal();
    await Promise.all([loadRankings(), loadSchedule(), loadItems(), loadVideos()]);
  }
  document.addEventListener('DOMContentLoaded', init);
})();