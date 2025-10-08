// static/js/app.js (rev2)

(function () {
  const $  = (q, r=document) => r.querySelector(q);
  const $$ = (q, r=document) => Array.from(r.querySelectorAll(q));

  const FILTER_KEY = "newsFilter";
  const SAVED_KEY  = "savedArticles";

  const store = {
    get(k,d){ try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k,v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }
  };

  // ----- time helpers
  const normalizeTS = (ts) => {
    if (typeof ts === "string") ts = Number(ts);
    if (ts < 1e12) ts = ts * 1000; // seconds -> ms
    return ts;
  };
  const timeAgo = (ts)=>{
    ts = normalizeTS(ts);
    const diff = Math.max(0, Date.now() - ts);
    const m = Math.floor(diff/60000);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m/60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h/24);
    return `${d}d ago`;
  };

  // ----- seed & fetch
  function getSeedItems(){
    const t=$("#seed-items");
    if (!t) return [];
    try { return (JSON.parse(t.textContent).items||[]).map(i=>({...i, ts: normalizeTS(i.ts)})); }
    catch { return []; }
  }
  async function fetchNews(){
    try{
      const r = await fetch("./static/data/news.json?v="+Date.now(), { cache:"no-store" });
      if (!r.ok) throw 0;
      const j = await r.json();
      (j.items||[]).forEach(i=>i.ts = normalizeTS(i.ts));
      return j;
    }catch{
      return { items: getSeedItems(), updated: Date.now() };
    }
  }

  // ----- UI helpers
  const hash=(s)=>{let h=0;for(let i=0;i<s.length;i++){h=((h<<5)-h)+s.charCodeAt(i);h|=0;}return"h"+Math.abs(h);};

  function initPills(){
    const pills = $$("#filterPills .pill");
    const last = store.get(FILTER_KEY, "all");
    pills.forEach(p => { if (p.dataset.filter===last) p.classList.add("active"); });
    pills.forEach(p => p.addEventListener("click", ()=>{
      pills.forEach(x=>x.classList.remove("active"));
      p.classList.add("active");
      store.set(FILTER_KEY, p.dataset.filter);
      render();
    }));
  }

  function cardHTML(it, savedSet){
    const lock = it.paywall ? "🔒" : "";
    const img  = it.image ? `<div class="card-thumb"><img loading="lazy" src="${it.image}" alt=""></div>` : "";
    const id   = hash(it.link);
    const saved= savedSet.has(id);
    return `
    <article class="card ${it.tier}">
      ${img}
      <div class="card-body">
        <div class="card-kickers">
          <span class="kicker">${it.tier}</span>
          <span class="kicker src">${it.source}${lock}</span>
        </div>
        <a class="card-title" href="${it.link}" target="_blank" rel="noopener">${it.title}</a>
        <div class="card-meta" data-ts="${it.ts}">
          <span class="ago">${timeAgo(it.ts)}</span> • ${it.source}
        </div>
        <div class="card-actions">
          <button class="btn-icon copy" data-url="${it.link}" title="Copy link">⎘</button>
          <button class="btn-icon save" data-id="${id}" title="${saved?'Remove':'Save'}">${saved?'★':'☆'}</button>
        </div>
      </div>
    </article>`;
  }

  function attachCardEvents(root){
    root.querySelectorAll(".btn-icon.copy").forEach(btn=>{
      btn.addEventListener("click", async ()=>{
        const url = btn.getAttribute("data-url");
        try { await navigator.clipboard.writeText(url); btn.textContent="✓"; setTimeout(()=>btn.textContent="⎘",900);} catch {}
      });
    });
    root.querySelectorAll(".btn-icon.save").forEach(btn=>{
      btn.addEventListener("click", ()=>{
        const id = btn.getAttribute("data-id");
        const saved = new Set(store.get(SAVED_KEY, []));
        if (saved.has(id)) { saved.delete(id); btn.textContent="☆"; }
        else               { saved.add(id);    btn.textContent="★"; }
        store.set(SAVED_KEY, Array.from(saved));
      });
    });
  }

  // ----- render headlines + insiders
  let cache=null;
  async function render(){
    const grid=$("#news-grid"), heroW=$("#news-hero"), heroM=$("#news-hero-meta");
    if (!grid || !heroW) return;

    if (!cache){
      $("#news-status")?.removeAttribute("hidden");
      cache = await fetchNews();
      $("#news-status")?.setAttribute("hidden","");
    }

    const filter = store.get(FILTER_KEY, "all");
    const savedSet = new Set(store.get(SAVED_KEY, []));

    let list = cache.items || [];
    if (filter !== "all") list = list.filter(it => it.tier.startsWith(filter));

    // HERO
    const hero = list.find(x => !!x.image) || list[0];
    if (hero) {
      heroW.innerHTML = hero.image ? `<a class="hero-img" href="${hero.link}" target="_blank"><img src="${hero.image}" alt=""></a>` : "";
      heroM.innerHTML = `
        <div class="meta-row"><span class="pill small">${hero.tier}</span><span class="pill small">${hero.source}</span></div>
        <a class="hero-title" href="${hero.link}" target="_blank">${hero.title}</a>
        <div class="muted small">${timeAgo(hero.ts)}</div>`;
    }

    const rest = list.filter(x => !hero || x.link !== hero.link);
    grid.innerHTML = rest.slice(0, 21).map(it => cardHTML(it, savedSet)).join("");
    attachCardEvents(grid);

    // Insider / Beat Links (last 6)
    const insiders = (cache.items||[]).filter(i => i.tier === "insiders").slice(0,6);
    const inEl = $("#insiderList");
    if (inEl) {
      if (!insiders.length) {
        inEl.innerHTML = `<div class="muted small">No insider items (yet).</div>`;
      } else {
        inEl.innerHTML = insiders.map(i =>
          `<a class="link-card clickable" href="${i.link}" target="_blank" rel="noopener">
             <div class="link-body">
               <div class="link-title">${i.title}</div>
               <div class="link-meta">${i.source} • ${timeAgo(i.ts)}</div>
             </div>
           </a>`
        ).join("");
      }
    }
  }

  // tick timestamps
  setInterval(()=>{$$(".card-meta").forEach(e=>{const ts=+e.getAttribute("data-ts"); if(ts){$(".ago",e).textContent=timeAgo(ts);} });},60000);

  // keyboard nav
  document.addEventListener("keydown", e=>{
    if (!["ArrowRight","ArrowLeft","ArrowDown","ArrowUp","j","k"].includes(e.key)) return;
    const cards=$$(".card-title"); if(!cards.length) return;
    const a=document.activeElement; let i=cards.indexOf(a);
    if (["ArrowRight","ArrowDown","j"].includes(e.key)) i++;
    if (["ArrowLeft","ArrowUp","k"].includes(e.key)) i--;
    i=Math.max(0,Math.min(cards.length-1,i)); cards[i].focus();
  });

  // ----- roster (visible messages when missing)
  async function hydrateRoster(){
    const el=$("#rosterGrid"), stamp=$("#rosterStamp");
    if(!el) return;
    try{
      const r = await fetch("./static/teams/purdue-mbb/roster.json?v="+Date.now(), { cache:"no-store" });
      if(!r.ok){ el.innerHTML=`<div class="muted small">Roster file missing.</div>`; return; }
      const j = await r.json();
      const players = j.players || [];
      if(!players.length){ el.innerHTML=`<div class="muted small">No roster data.</div>`; return; }
      el.innerHTML = players.map(p => `
        <div class="player">
          <div class="num">#${p.num ?? ""}</div>
          <div class="name">${p.name ?? ""}</div>
          <div class="meta">${[p.pos, p.height, p.weight ? `${p.weight} lbs` : "", p.year].filter(Boolean).join(" • ")}</div>
        </div>`).join("");
      if (j.updated) stamp.textContent = "Updated " + new Date(j.updated).toLocaleString();
    }catch{ el.innerHTML=`<div class="muted small">Failed to load roster.</div>`; }
  }

  // ----- boot (also kicks schedule via PRO if available)
  function boot(){
    initPills();
    render();
    if (window.PRO && typeof window.PRO.hydratePanels === "function") window.PRO.hydratePanels();
    hydrateRoster();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once:true });
  else boot();
})();