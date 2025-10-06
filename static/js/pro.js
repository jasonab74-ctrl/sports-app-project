/* pro.js — Panels (Rankings, Insiders, Roster, Schedule) with graceful fallbacks.
   Safe for GitHub Pages. No globals except window.PRO. */

(function(){
  const defaultBase = '/sports-app-project/';
  const byId = (id) => document.getElementById(id);
  const esc = (s='') => (s+'').replace(/[&<>"']/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  const urlFor = (base, p) => `${base}${p.replace(/^\//,'')}`;

  // ---- Rankings ----
  function renderRankings(widgets){
    if (!widgets || typeof widgets !== 'object') return;
    const ap = byId('apRank');
    const kp = byId('kpRank');
    const apL = byId('apLink');
    const kpL = byId('kpLink');
    const upd = byId('rankUpdated');

    const hasAP = Number.isFinite(widgets.ap_rank);
    const hasKP = Number.isFinite(widgets.kenpom_rank);

    if (ap) ap.textContent = hasAP ? `#${widgets.ap_rank}` : '—';
    if (kp) kp.textContent = hasKP ? `#${widgets.kenpom_rank}` : '—';

    if (apL){ 
      if (hasAP && widgets.ap_url){ apL.href = widgets.ap_url; apL.hidden = false; }
      else { apL.hidden = true; }
    }
    if (kpL){
      if (hasKP && widgets.kenpom_url){ kpL.href = widgets.kenpom_url; kpL.hidden = false; }
      else { kpL.hidden = true; }
    }

    // Show "as of" only if at least one value exists
    if (upd){
      if ((hasAP || hasKP) && widgets.updated_at){
        try {
          const dt = new Date(widgets.updated_at);
          upd.textContent = `as of ${dt.toLocaleString([], {month:'short', day:'numeric'})}`;
        } catch { upd.textContent = ''; }
      } else {
        upd.textContent = '';
      }
    }
  }

  // ---- Insiders ----
  function timeAgo(iso){
    try {
      const diffM = (Date.now() - new Date(iso).getTime())/60000;
      if (diffM < 60) return `${Math.round(diffM)}m ago`;
      if (diffM < 1440) return `${Math.round(diffM/60)}h ago`;
      return `${Math.round(diffM/1440)}d ago`;
    } catch { return ''; }
  }

  function renderInsiders(list){
    const el = byId('insiderList');
    if (!el) return;
    if (!Array.isArray(list) || !list.length){
      el.innerHTML = '';
      return;
    }
    el.innerHTML = list.map(o=>{
      const pay = o.pay ? '<span class="badge-pay">$</span>' : '';
      const sub = o.latest_headline ? `<div class="link-meta">${esc(o.latest_headline)}</div>` : '';
      const meta = o.updated_at ? ` • ${timeAgo(o.updated_at)}` : '';
      const link = o.latest_url || o.url || '#';
      const type = esc(o.type || '');
      return `<a class="link-card" href="${link}" target="_blank" rel="noopener">
        <div class="link-logo">📰</div>
        <div class="link-body"><div class="link-title">${esc(o.name||'Source')}</div>${sub}</div>
        <div class="link-meta">${type}${pay}${meta}</div>
      </a>`;
    }).join('');
  }

  // ---- Roster ----
  function renderRoster(roster){
    const el = byId('rosterGrid');
    if (!el) return;
    if (!Array.isArray(roster) || !roster.length){
      el.innerHTML = '';
      return;
    }
    // Sort by jersey number if available
    const sorted = roster.slice().sort((a,b)=> (a.num||999)-(b.num||999));
    el.innerHTML = sorted.map(p=>`
      <div class="roster-card">
        <div class="roster-num">#${esc(p.num||'?')} — ${esc(p.name||'Player')}</div>
        <div class="roster-meta">
          ${esc(p.pos||'')}${p.ht?` • ${esc(p.ht)}`:''}${p.wt?` • ${esc(p.wt)} lbs`:''}${p.class?` • ${esc(p.class)}`:''}
        </div>
        ${p.hometown?`<div class="roster-meta">${esc(p.hometown)}</div>`:''}
      </div>
    `).join('');
  }

  // ---- Schedule ----
  function initials(name='?'){
    try{
      const clean = (name||'').replace(/^[@vs]\s*/,'').replace(/\(.*?\)/g,'').trim();
      const parts = clean.split(/\s+/);
      return (parts[0]?.[0]||'').toUpperCase() + (parts[1]?.[0]||'').toUpperCase();
    }catch{return '•'}
  }
  function renderSchedule(sched){
    const el = byId('scheduleList');
    if (!el) return;
    if (!Array.isArray(sched) || !sched.length){
      el.innerHTML = '';
      return;
    }
    const items = sched.slice(0,6).map(g=>{
      let dtTxt = '';
      try {
        const dt = new Date(g.utc || g.date);
        dtTxt = isNaN(dt.getTime()) ? (g.date||'') : dt.toLocaleString([], {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
      } catch {
        dtTxt = g.date || '';
      }
      const comp = g.comp ? `<span class="link-meta">${esc(g.comp)}</span>` : '';
      const site = g.site ? `<span class="link-meta"> • ${esc(g.site)}</span>` : '';
      const when = dtTxt ? `<span class="link-meta"> • ${esc(dtTxt)} local</span>` : '';
      return `<div class="link-card">
        <div class="link-logo">${esc(g.opponent?initials(g.opponent):'•')}</div>
        <div class="link-body">
          <div class="link-title">${esc(g.opponent||'TBD')}</div>
          <div class="link-meta">${comp}${site}${when}</div>
        </div>
      </div>`;
    });
    el.innerHTML = items.join('');
  }

  // ---- Public: hydratePanels ----
  async function hydratePanels(base = defaultBase){
    // Fetch all four in parallel; each is optional
    const [widgetsRes, insRes, rosRes, schRes] = await Promise.allSettled([
      fetch(urlFor(base, 'static/widgets.json'), {cache:'no-store'}),
      fetch(urlFor(base, 'static/insiders.json'), {cache:'no-store'}),
      fetch(urlFor(base, 'static/teams/purdue-mbb/roster.json'), {cache:'no-store'}),
      fetch(urlFor(base, 'static/schedule.json'), {cache:'no-store'})
    ]);

    if (widgetsRes.status === 'fulfilled' && widgetsRes.value.ok){
      try { renderRankings(await widgetsRes.value.json()); } catch {}
    }
    if (insRes.status === 'fulfilled' && insRes.value.ok){
      try { renderInsiders(await insRes.value.json()); } catch {}
    }
    if (rosRes.status === 'fulfilled' && rosRes.value.ok){
      try { renderRoster(await rosRes.value.json()); } catch {}
    }
    if (schRes.status === 'fulfilled' && schRes.value.ok){
      try { renderSchedule(await schRes.value.json()); } catch {}
    }
  }

  // Expose single entrypoint
  window.PRO = Object.freeze({ hydratePanels });
})();
