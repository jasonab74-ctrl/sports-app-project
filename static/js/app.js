// static/js/app.js
// Top Headlines: filters, live timestamps, save/copy, paywall locks, lazy images.

(function () {
  const $ = (q, r=document) => r.querySelector(q);
  const $$ = (q, r=document) => Array.from(r.querySelectorAll(q));

  const FILTER_KEY = "newsFilter";
  const SAVED_KEY  = "savedArticles";

  const store = {
    get(k,d){try{return JSON.parse(localStorage.getItem(k))??d;}catch{return d;}},
    set(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch{}}
  };

  const timeAgo = (ts)=>{
    const diff = Date.now()-ts;
    const m=Math.floor(diff/60000);
    if(m<60)return`${m}m ago`;
    const h=Math.floor(m/60);
    if(h<24)return`${h}h ago`;
    const d=Math.floor(h/24);
    return`${d}d ago`;
  };

  const hash=(s)=>{let h=0;for(let i=0;i<s.length;i++){h=((h<<5)-h)+s.charCodeAt(i);h|=0;}return"h"+Math.abs(h);};

  function getSeedItems(){
    const t=$("#seed-items");
    if(!t)return[];
    try{return JSON.parse(t.textContent).items||[];}catch{return[];}
  }

  async function fetchNews(){
    try{
      const r=await fetch("./static/data/news.json?v="+Date.now(),{cache:"no-store"});
      if(!r.ok)throw new Error("fetch failed");
      return await r.json();
    }catch{return{items:getSeedItems(),updated:Date.now()};}
  }

  function pillsInit(){
    const last=store.get(FILTER_KEY,"all");
    $$(".pills .pill").forEach(p=>{
      const val=p.textContent.trim().toLowerCase();
      if(val===last)p.classList.add("active");
      p.addEventListener("click",()=>{
        $$(".pills .pill").forEach(x=>x.classList.remove("active"));
        p.classList.add("active");
        store.set(FILTER_KEY,val==="all"?"all":val.replace(/s$/,""));
        render();
      });
    });
  }

  function cardHTML(it,savedSet){
    const locked=it.paywall?"🔒":"";
    const img=it.image?`<div class="card-thumb"><img loading="lazy" src="${it.image}" alt=""></div>`:"";
    const id=hash(it.link);
    const saved=savedSet.has(id);
    const saveIcon=saved?"★":"☆";
    const saveTitle=saved?"Remove":"Save";

    return`
    <article class="card ${it.tier}">
      ${img}
      <div class="card-body">
        <div class="card-kickers">
          <span class="kicker">${it.tier}</span>
          <span class="kicker src">${it.source}${locked}</span>
        </div>
        <a class="card-title" href="${it.link}" target="_blank" rel="noopener">${it.title}</a>
        <div class="card-meta" data-ts="${it.ts}">
          <span class="ago">${timeAgo(it.ts)}</span> • ${it.source}
        </div>
        <div class="card-actions">
          <button class="btn-icon copy" data-url="${it.link}" title="Copy link">⎘</button>
          <button class="btn-icon save" data-id="${id}" data-url="${it.link}" data-title="${it.title}" title="${saveTitle}">${saveIcon}</button>
        </div>
      </div>
    </article>`;
  }

  function attachCardEvents(root){
    root.querySelectorAll(".btn-icon.copy").forEach(btn=>{
      btn.addEventListener("click",async()=>{
        const url=btn.getAttribute("data-url");
        try{await navigator.clipboard.writeText(url);btn.textContent="✓";setTimeout(()=>btn.textContent="⎘",900);}catch{}
      });
    });
    root.querySelectorAll(".btn-icon.save").forEach(btn=>{
      btn.addEventListener("click",()=>{
        const id=btn.getAttribute("data-id");
        const saved=new Set(store.get(SAVED_KEY,[]));
        if(saved.has(id)){saved.delete(id);btn.textContent="☆";}
        else{saved.add(id);btn.textContent="★";}
        store.set(SAVED_KEY,Array.from(saved));
      });
    });
  }

  let cache=null;
  async function render(){
    const grid=$("#news-grid"),heroW=$("#news-hero"),heroM=$("#news-hero-meta");
    if(!grid||!heroW)return;
    if(!cache){$("#news-status")?.removeAttribute("hidden");cache=await fetchNews();$("#news-status")?.setAttribute("hidden","");}
    const filter=store.get(FILTER_KEY,"all");
    const saved=new Set(store.get(SAVED_KEY,[]));
    let list=cache.items||[];
    if(filter!=="all"){list=list.filter(it=>it.tier.startsWith(filter));}

    // HERO item
    const hero=list.find(x=>x.image)||list[0];
    if(hero){
      heroW.innerHTML=`<a class="hero-img" href="${hero.link}" target="_blank"><img src="${hero.image||""}" alt=""></a>`;
      heroM.innerHTML=`<div class="meta-row"><span class="pill small">${hero.tier}</span><span class="pill small">${hero.source}</span></div>
      <a class="hero-title" href="${hero.link}" target="_blank">${hero.title}</a>
      <div class="muted small">${timeAgo(hero.ts)}</div>`;
    }

    const rest=list.filter(x=>!hero||x.link!==hero.link);
    grid.innerHTML=rest.slice(0,21).map(it=>cardHTML(it,saved)).join("");
    attachCardEvents(grid);
  }

  setInterval(()=>{$$(".card-meta").forEach(e=>{const ts=+e.getAttribute("data-ts");if(ts)$(".ago",e).textContent=timeAgo(ts);});},60000);

  document.addEventListener("keydown",e=>{
    if(!["ArrowRight","ArrowLeft","ArrowDown","ArrowUp","j","k"].includes(e.key))return;
    const cards=$$(".card-title");if(!cards.length)return;
    const a=document.activeElement;let i=cards.indexOf(a);
    if(e.key==="ArrowRight"||e.key==="ArrowDown"||e.key==="j")i++;
    if(e.key==="ArrowLeft"||e.key==="ArrowUp"||e.key==="k")i--;
    i=Math.max(0,Math.min(cards.length-1,i));
    cards[i].focus();
  });

  pillsInit();
  render();
})();
