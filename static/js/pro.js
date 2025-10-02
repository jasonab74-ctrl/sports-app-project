
(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);
  const $$ = (sel, ctx=document) => Array.from(ctx.querySelectorAll(sel));

  // Basic state
  let team = { name: "Purdue Men's Basketball", slug: "purdue-mbb" };
  // Attempt to load team.json if present
  fetch('static/team.json').then(r=>r.ok?r.json():null).then(j=>{ if(j){ team = j } init(); }).catch(()=>init());

  function init(){
    bindNav();
    loadTicker();
    loadItems();
    loadRankings();
    loadSchedule();
    loadInsiders();
    loadVideos();
    setupModal();
  }

  function bindNav(){
    const navToggle = $('#navToggle');
    const nav = $('#mainNav');
    navToggle.addEventListener('click', () => {
      const open = navToggle.getAttribute('aria-expanded') === 'true';
      navToggle.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('open');
    });
  }

  function ftimeAgo(date){
    try{
      const d = new Date(date);
      const diff = (Date.now()-d.getTime())/1000;
      if (diff < 90) return 'just now';
      const units = [
        ['y', 31536000], ['mo', 2592000], ['d', 86400], ['h', 3600], ['m', 60]
      ];
      for (const [label, secs] of units){
        const v = Math.floor(diff/secs);
        if (v >= 1) return `${v}${label} ago`;
      }
      return 'just now';
    }catch(e){ return ''}
  }

  function loadTicker(){
    // Build ticker from latest 8 headlines after items load
  }

  async function loadItems(){
    try{
      const url = `static/teams/${team.slug}/items.json`;
      const res = await fetch(url, {cache:'no-cache'});
      const data = await res.json();
      const items = (data.items || data || []).slice(0, 18);

      // Ticker
      const tt = $('#tickerTrack');
      tt.innerHTML = items.slice(0,12).map(i => `<span style="margin:0 1.25rem">${escapeHTML(i.source||'')} — ${escapeHTML(i.title||'')}</span>`).join('');

      // Hero
      const hero = $('#hero');
      if(items.length){
        const lead = items[0];
        hero.classList.remove('skeleton');
        hero.innerHTML = `
          <a href="${lead.link}" target="_blank" rel="noopener" class="hero-img-wrap">
            <img class="hero-img" src="${lead.image||''}" alt="" loading="eager" decoding="async"/>
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

      // Cards
      const grid = $('#headlines');
      grid.innerHTML = items.slice(1).map(renderCard).join('');

      // Footer freshness
      $('#updatedFooter').textContent = `Updated ${new Date().toLocaleString([], {hour:'2-digit', minute:'2-digit'})}`;
      $('#sourceCount').textContent = data.sources ? `• ${data.sources.length} sources` : '';
    }catch(e){
      console.error(e);
    }
  }

  function badge(tag){
    const t = (tag||'').toLowerCase();
    if (t.includes('official')) return `<span class="pill">official</span>`;
    if (t.includes('insider')) return `<span class="pill">insider</span>`;
    if (t.includes('national')) return `<span class="pill">national</span>`;
    return t ? `<span class="pill">${escapeHTML(t)}</span>` : '';
  }

  function renderCard(i){
    const when = ftimeAgo(i.date||i.published||new Date().toISOString());
    const img = i.image || '';
    return `
      <article class="card">
        <a class="card-img-wrap" href="${i.link}" target="_blank" rel="noopener">
          <img class="card-img" src="${img}" alt="" loading="lazy" decoding="async">
        </a>
        <div class="card-body">
          <div class="card-meta">${badge(i.tier||i.tag)} <span>${escapeHTML(i.source||'')}</span> • <span>${when}</span></div>
          <a class="card-title" href="${i.link}" target="_blank" rel="noopener">${escapeHTML(i.title||'')}</a>
        </div>
      </article>
    `;
  }

  async function loadRankings(){
    try{
      const res = await fetch('static/widgets.json', {cache:'no-cache'});
      const w = await res.json();
      $('#apRank').textContent = w.ap_rank ? `#${w.ap_rank}` : '—';
      $('#kpRank').textContent = w.kenpom_rank ? `#${w.kenpom_rank}` : '—';
      if (w.ap_url) $('#apLink').href = w.ap_url;
      if (w.kenpom_url) $('#kpLink').href = w.kenpom_url;
      if (w.updated_at){
        const ts = new Date(w.updated_at);
        $('#rankUpdated').textContent = `as of ${ts.toLocaleString([], {month:'short', day:'numeric'})}`;
      }
    }catch(e){}
  }

  async function loadSchedule(){
    try{
      const res = await fetch('static/schedule.json', {cache:'no-cache'});
      const sched = await res.json();
      const list = $('#scheduleList');
      list.innerHTML = sched.slice(0,6).map(g => {
        const dt = new Date(g.utc || g.date);
        const time = dt.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
        const day = dt.toLocaleDateString([], {year:'numeric', month:'2-digit', day:'2-digit'});
        const site = g.site || 'TBD';
        const tag = `<span class="tag">${site}</span>`;
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        return `<a class="game" href="${g.espn_url||'#'}" target="_blank" rel="noopener">
          <div class="g-top"><span>${day}</span><span>${time} <small>${tz.split('/').pop()}</small></span></div>
          <div class="g-title">${escapeHTML(g.opp||'Opponent')} ${tag}</div>
        </a>`;
      }).join('');
    }catch(e){}
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

  async function loadVideos(){
    try{
      const res = await fetch(`static/teams/${team.slug}/items.json`, {cache:'no-cache'});
      const data = await res.json();
      const videos = (data.items || data || []).filter(i => (i.type||'').includes('video') || /youtube\.com|youtu\.be/.test(i.link||'')).slice(0,8);
      const grid = $('#videoGrid');
      grid.innerHTML = videos.map(v => {
        const id = ytId(v.link||'');
        const thumb = v.image || (id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : '');
        return `<article class="video">
          <a class="video-thumb" href="${v.link}" data-yt="${id||''}">
            <img src="${thumb}" alt="" loading="lazy" decoding="async">
            ${v.duration ? `<span class="video-duration">${v.duration}</span>`:''}
          </a>
          <div class="video-body">
            <div class="video-title"><a href="${v.link}" data-yt="${id||''}">${escapeHTML(v.title||'')}</a></div>
            <div class="video-meta">${escapeHTML(v.source||'')} • ${ftimeAgo(v.date||v.published||new Date().toISOString())}</div>
          </div>
        </article>`;
      }).join('');

      // click -> modal
      grid.addEventListener('click', (e) => {
        const a = e.target.closest('a[data-yt]');
        if(!a) return;
        const id = a.getAttribute('data-yt');
        if(!id) return;
        e.preventDefault();
        openModal(id);
      });
    }catch(e){}
  }

  function ytId(url){
    try{
      const u = new URL(url);
      if (u.hostname.includes('youtu.be')) return u.pathname.slice(1);
      if (u.searchParams.get('v')) return u.searchParams.get('v');
      const m = /\/embed\/([^?]+)/.exec(u.pathname);
      if (m) return m[1];
      return null;
    }catch(_){ return null }
  }

  function setupModal(){
    const modal = $('#videoModal');
    modal.addEventListener('click', (e) => {
      if (e.target.hasAttribute('data-close')) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if(e.key === 'Escape') closeModal();
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

  function escapeHTML(s){ return (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }

})();
