// static/js/pro.js
// Panels hydration for Rankings / Schedule / Insiders / Roster
// Safe to include even if some JSON files are missing.

(function(){
  const BASE = "./";
  const url = (p) => BASE + p.replace(/^\//,'');
  const $ = (id) => document.getElementById(id);

  function fmtLocal(iso) {
    try {
      const dt = new Date(iso);
      const d = dt.toLocaleDateString([], { month:'2-digit', day:'2-digit' });
      const t = dt.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
      return `${d}, ${t} local`;
    } catch {
      return iso;
    }
  }

  function pill(text){ return `<span class="pill">${escapeHtml(text)}</span>`; }
  function escapeHtml(s=''){return (s+'').replace(/[&<>"']/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#39;' }[c]));}

  async function loadJSON(path){
    try{
      const res = await fetch(url(path), { cache: 'no-store' });
      if (!res.ok) throw new Error(res.statusText);
      return await res.json();
    }catch(e){ return null; }
  }

  /* ========== SCHEDULE ========== */
  function renderSchedule(data){
    const mount = $("scheduleList");
    if (!mount) return;
    if (!data || !Array.isArray(data.games) || !data.games.length){
      mount.innerHTML = `<div class="muted small">No upcoming games.</div>`;
      return;
    }

    // Only show upcoming (>= now - 3 hrs safety)
    const now = Date.now() - 3*60*60*1000;
    const upcoming = data.games.filter(g => new Date(g.utc).getTime() >= now).slice(0,8);

    mount.innerHTML = upcoming.map(g=>{
      const odds = Array.isArray(g?.odds?.consensus) ? g.odds.consensus : [];
      // pick a "headline" book row if any have spread
      let head = odds.find(o => o.spread !== null && o.spread !== undefined) || odds[0];
      const oddsLine = head
        ? `<div class="link-meta">Odds: <strong>${escapeHtml(head.book)}</strong> • ${head.spread !== null && head.spread !== undefined ? `Spread: ${head.spread}` : ''} ${head.total? ` • Total: ${head.total}` : ''} ${head.moneyline? ` • ML: ${head.moneyline}` : ''}</div>`
        : '';

      return `
        <a class="link-card" href="${'#'}" tabindex="0">
          <div class="link-logo">•</div>
          <div class="link-body">
            <div class="link-title">${escapeHtml(g.opponent || "TBD")}</div>
            <div class="link-meta">• ${escapeHtml(g.venue || 'Neutral')}</div>
            <div class="link-meta">• ${fmtLocal(g.utc)}</div>
            ${oddsLine}
          </div>
        </a>`;
    }).join("");
  }

  /* ========== (stubs) RANKINGS/INSIDERS/ROSTER keep as-is if you already have them ==========
     This file only adds schedule logic. If you had additional logic earlier, keep it above or below.
  */

  async function hydratePanels(basePrefix){
    // Schedule
    const sched = await loadJSON("static/teams/purdue-mbb/schedule.json");
    renderSchedule(sched);

    // If you previously had other panel fetches here, you can leave them as-is or add them back.
    // Example (commented):
    // const ranks = await loadJSON("static/teams/purdue-mbb/rankings.json"); renderRankings(ranks);
    // const insiders = await loadJSON("static/teams/purdue-mbb/insiders.json"); renderInsiders(insiders);
    // const roster = await loadJSON("static/teams/purdue-mbb/roster.json"); renderRoster(roster);
  }

  window.PRO = window.PRO || {};
  window.PRO.hydratePanels = hydratePanels;

})();
