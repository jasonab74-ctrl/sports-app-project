// static/js/pro.js — schedule panel + odds + stamps (exhibitions & tourneys included)
(function () {
  const BASE = "./";
  const url = (p) => BASE + p.replace(/^\//, "");
  const $  = (id) => document.getElementById(id);

  const esc = (s="") => (s+"").replace(/[&<>"']/g, c=>({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
  const tzAbbr = (d=new Date()) => {
    try{ return d.toLocaleTimeString([], { timeZoneName:"short" }).split(" ").pop() || "local"; }catch{ return "local"; }
  };
  const fmtLocal = (iso)=>{
    try{
      const dt=new Date(iso);
      const d = dt.toLocaleDateString([], { weekday:"short", month:"2-digit", day:"2-digit" });
      const t = dt.toLocaleTimeString([], { hour:"numeric", minute:"2-digit" });
      return `${d}, ${t} ${tzAbbr(dt)}`;
    }catch{return iso;}
  };

  async function load(path){
    try{
      const r = await fetch(url(path)+`?v=${Date.now()}`, { cache:"no-store" });
      if (!r.ok) throw 0;
      return await r.json();
    }catch{return null;}
  }

  function line(label, value){
    if (!value) return "";
    return `<div class="link-meta">${label}: ${esc(value)}</div>`;
  }

  function renderSchedule(data){
    const el = $("scheduleList");
    const stamp = $("schedStamp");
    if (!el) return;

    if (!data){
      el.innerHTML = `<div class="muted small">Failed to load schedule.</div>`;
      return;
    }
    if (data.updated && stamp){
      try{ stamp.textContent = "Updated " + new Date(data.updated).toLocaleString(); }catch{}
    }

    const now = Date.now() - 3*60*60*1000; // show near-past start too
    const upcoming = (data.games||[]).filter(g=> new Date(g.utc).getTime() >= now).slice(0, 12);
    if (!upcoming.length){
      el.innerHTML = `<div class="muted small">No upcoming games.</div>`;
      return;
    }
    el.innerHTML = upcoming.map(g=>{
      const odds = Array.isArray(g?.odds?.consensus) ? g.odds.consensus : [];
      const head = odds.find(o => o.spread!==null && o.spread!==undefined) || odds[0];
      const oddsLine = head
        ? `Odds: ${esc(head.book)}${head.spread!==null&&head.spread!==undefined?` • Spread: ${head.spread}`:""}${head.total?` • Total: ${head.total}`:""}${head.moneyline?` • ML: ${head.moneyline}`:""}`
        : "";

      return `
        <div class="link-card schedule-card">
          <div class="link-body">
            <div class="link-title">${esc(g.opponent || "TBD")}</div>
            <div class="link-meta">${esc(g.venue || "Neutral")}</div>
            <div class="link-meta">${fmtLocal(g.utc)}</div>
            ${line("Event", g.event)}
            ${line("TV", g.tv)}
            ${line("Location", g.location)}
            ${oddsLine ? `<div class="link-meta">${oddsLine}</div>` : ""}
            ${g.url ? `<div class="link-meta"><a class="muted" href="${esc(g.url)}" target="_blank" rel="noopener">Game details ↗</a></div>` : ""}
          </div>
        </div>`;
    }).join("");
  }

  async function hydratePanels(){
    const schedule = await load("static/teams/purdue-mbb/schedule.json");
    renderSchedule(schedule);
  }

  window.PRO = window.PRO || {};
  window.PRO.hydratePanels = hydratePanels;
})();