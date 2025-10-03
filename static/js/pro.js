(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);

  // GitHub Pages base path for safety (still used if you keep external JSONs)
  const PATH_BASE = '/sports-app-project/';
  const url = (p) => `${PATH_BASE}${p.replace(/^\//,'')}`;

  // Optional proxy (leave empty if you didn't deploy a Worker)
  const PROXY_BASE = "";
  const PROXY_HOSTS = new Set([
    'img.si.com','si.com','gannett-cdn.com','jconline.com','s.yimg.com','yimg.com','yahoo.com',
    '247sports.imgix.net','247sports.com','rivalscdn.com','rivals.com','sportshqimages.cbsimg.net','cbssports.com',
    'vox-cdn.com','sbnation.com','espncdn.com','espn.com','apnews.com','nbcsports.com','i.ytimg.com','ytimg.com','youtube.com',
    'purduesports.com'
  ]);

  // ---------- Utils ----------
  const escapeHTML = (s) => (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  function ftimeAgo(date){ try{const d=new Date(date);const diff=(Date.now()-d.getTime())/1000;if(diff<90)return'just now';const u=[['y',31536000],['mo',2592000],['d',86400],['h',3600],['m',60]];for(const [l,s] of u){const v=Math.floor(diff/s);if(v>=1)return`${v}${l} ago`;}return'just now';}catch(_){return''} }
  const etld1 = (host) => { if(!host) return ''; const p=host.toLowerCase().split('.').filter(Boolean); return p.length<=2?host.toLowerCase():p.slice(-2).join('.'); };
  const setDebug = (msg) => { const el=$('#debugMsg'); if(el) el.textContent=msg; console.log('[DEBUG]', msg); };

  function initialsFrom(str=''){ const parts=(str||'').trim().split(/\s+/); const a=(parts[0]||'')[0]||''; const b=(parts[1]||'')[0]||''; return (a+b).toUpperCase() || '•'; }
  function fallbackNode(aspect,label){ const div=document.createElement('div'); div.className=aspect==='16x9'?'fallback-16x9':'fallback-4x3'; const inner=document.createElement('div'); inner.className='fallback-badge'; inner.textContent=initialsFrom(label); div.appendChild(inner); return div; }
  function attachImgFallbacks(ctx=document){ ctx.querySelectorAll('img[data-aspect]').forEach(img=>{ const a=img.getAttribute('data-aspect'); const l=img.getAttribute('data-label')||''; img.addEventListener('error',()=>{ img.replaceWith(fallbackNode(a,l)); },{once:true}); }); }

  // ---------- Images ----------
  function ytId(urlStr){ try{const u=new URL(urlStr); if(u.hostname.includes('youtu.be')) return u.pathname.slice(1); if(u.searchParams.get('v')) return u.searchParams.get('v'); const m=/\/embed\/([^?]+)/.exec(u.pathname); return m?m[1]:null;}catch(_){return null} }
  const ytThumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
  function isLikelyBadImage(src){ if(!src) return true; const s=src.toLowerCase();
    if(/(sprite|logo|placeholder|default|blank|spacer)\.(png|svg|gif)$/.test(s)) return true;
    if(!/\.(jpg|jpeg|png|webp)(\?|$)/.test(s)) return true; return false; }
  function proxify(src){ if(!PROXY_BASE) return src; try{ const h=etld1(new URL(src).host.toLowerCase()); if(PROXY_HOSTS.has(h)) return `${PROXY_BASE}/?u=${encodeURIComponent(src)}`; return src; }catch{ return src; } }
  function selectImageForItem(item){ const id=ytId(item.link||''); if(id) return ytThumb(id); const c=item.image||''; if(!c||isLikelyBadImage(c)) return ''; return proxify(c); }

  // ---------- Render helpers ----------
  function badge(tag){ const t=(tag||'').toLowerCase(); if(t.includes('official'))return`<span class="pill">official</span>`; if(t.includes('insider'))return`<span class="pill">insiders</span>`; if(t.includes('national'))return`<span class="pill">national</span>`; return t?`<span class="pill">${escapeHTML(t)}</span>`:''; }

  function renderRankings(w){
    if(!w) return;
    $('#apRank').textContent = w.ap_rank ? `#${w.ap_rank}` : '—';
    $('#kpRank').textContent = w.kenpom_rank ? `#${w.kenpom_rank}` : '—';
    if (w.ap_url) $('#apLink').href = w.ap_url;
    if (w.kenpom_url) $('#kpLink').href = w.kenpom_url;
    if (w.updated_at){
      const ts=new Date(w.updated_at);
      $('#rankUpdated').textContent = `as of ${ts.toLocaleString([], {month:'short', day:'numeric'})}`;
    }
  }

  function initials(name='?'){
    const clean = name.replace(/^[@vs]\s*/,'').replace(/\(.*?\)/g,'');
    const parts = clean.trim().split(/\s+/);
    const letters = (parts[0][0]||'').toUpperCase() + ((parts[1]||'')[0]||'').toUpperCase();
    return letters || '•';
  }
  function siteClass(site){ const s=(site||'').toLowerCase(); if(s.startsWith('home'))return'site-home'; if(s.startsWith('away'))return'site-away'; if(s.startsWith('neutral'))return'site-neutral'; return''; }

  function renderSchedule(sched=[]){
    const list=$('#scheduleList');
    list.innerHTML = (sched||[]).slice(0,6).map(g=>{
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

  function renderItems(data){
    const items = (data.items || data || []);
    const list = items.slice(0,18);

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

  function renderInsiders(list){
    const el=$('#insiderList');
    el.innerHTML=(list||[]).map(o=>{
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

  // ---------- Boot ----------
  async function init(){
    // 1) Try inline data first
    const bootEl = document.getElementById('boot');
    if (bootEl) {
      try {
        const boot = JSON.parse(bootEl.textContent || '{}');
        renderRankings(boot.widgets);
        renderSchedule(boot.schedule);
        renderItems(boot.items);
        renderInsiders(boot.insiders);
        return; // we’re done; no fetches needed
      } catch (e) {
        setDebug('inline boot data parse error');
      }
    }

    // 2) Fallback to external JSONs (if you keep them)
    try {
      const [widgets, schedule, items, insiders] = await Promise.all([
        fetch(url('static/widgets.json')).then(r=>r.ok?r.json():null).catch(()=>null),
        fetch(url('static/schedule.json')).then(r=>r.ok?r.json():null).catch(()=>null),
        fetch(url('static/teams/purdue-mbb/items.json')).then(r=>r.ok?r.json():null).catch(()=>null),
        fetch(url('static/insiders.json')).then(r=>r.ok?r.json():null).catch(()=>null)
      ]);
      renderRankings(widgets);
      renderSchedule(schedule);
      renderItems(items||{items:[]});
      renderInsiders(insiders||[]);
    } catch (e) {
      setDebug('external fetch error');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();