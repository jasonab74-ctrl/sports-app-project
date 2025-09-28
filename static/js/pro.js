async function loadJSON(path){
  const r = await fetch(path + (path.includes("?")?"":"?ts="+Date.now()), {cache:"no-store"});
  if(!r.ok) throw new Error("HTTP " + r.status + " for " + path);
  return await r.json();
}

function setTheme(t){
  document.documentElement.style.setProperty("--primary", t.primary_color || "#004C54");
  document.documentElement.style.setProperty("--secondary", t.secondary_color || "#A5ACAF");
  document.documentElement.style.setProperty("--bg", t.dark_bg || "#0a1114");
  document.documentElement.style.setProperty("--panel", t.light_bg || "#0f1a1e");
  const hero = document.querySelector(".hero .image");
  hero.style.backgroundImage = `url('${t.hero_image}')`;
  const logo = document.getElementById("logo");
  logo.src = t.logo_url;
  document.getElementById("wordmark").textContent = t.wordmark || t.team_name || "Team Hub";
  const nav = document.querySelector(".nav");
  nav.innerHTML = "";
  (t.links||[]).forEach(l=>{
    const a = document.createElement("a");
    a.href = l.href; a.textContent = l.label;
    nav.appendChild(a);
  });
}

function fmtWhen(iso){
  if(!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {month:"short", day:"numeric", hour:"numeric", minute:"2-digit"});
}

function cardHTML(it){
  const img = it.image_url ? `<img src="${it.image_url}" alt="">` : "";
  return `<article class="card">
    <a class="thumb" href="${it.url}" target="_blank" rel="noopener">${img}</a>
    <div class="meta"><span class="badge">${(it.trust_level||"").replace("_"," ")}</span><span>${it.source||""}</span><span>•</span><time>${fmtWhen(it.published_at)}</time></div>
    <a class="title" href="${it.url}" target="_blank" rel="noopener">${it.title||""}</a>
    ${it.summary?`<p class="summary">${it.summary}</p>`:""}
  </article>`;
}

function render(items){
  const videos = items.filter(i=> (i.type||"").toLowerCase().includes("video")).slice(0,8);
  const news = items.filter(i=> !((i.type||"").toLowerCase().includes("video"))).slice(0,24);

  document.getElementById("newsGrid").innerHTML = news.map(cardHTML).join("");

  document.getElementById("videoRow").innerHTML = videos.map(i=> `<article class="card video-card">
    <a class="thumb" href="${i.url}" target="_blank" rel="noopener">${i.image_url?`<img src="${i.image_url}" alt="">`:""}</a>
    <a class="title" href="${i.url}" target="_blank" rel="noopener">${i.title||""}</a>
    <div class="meta"><span>${i.source||""}</span><span>•</span><time>${fmtWhen(i.published_at)}</time></div>
  </article>`).join("");

  const sched = [
    {date:"Oct 30", opp:"Exhibition", where:"Home", time:"7:00p"},
    {date:"Nov 05", opp:"Indiana State", where:"Home", time:"7:00p"},
    {date:"Nov 12", opp:"@ Marquette", where:"Away", time:"8:30p"}
  ];
  document.getElementById("scheduleList").innerHTML = sched.map(g=>`
    <div class="game"><div><div class="date">${g.date}</div><div class="opp">${g.opp}</div></div><div>${g.where} • ${g.time}</div></div>
  `).join("");

  document.getElementById("socialCol").innerHTML = `
    <div class="x-embed">Follow on X: <strong>@${(window.theme && window.theme.team_name) ? window.theme.team_name.replace(/\s+/g,'') : 'Team'}</strong><br/>Embed live feed here later.</div>
  `;
}

async function main(){
  try{
    const t = await loadJSON("./static/team.json"); window.theme = t; setTheme(t);
  }catch(e){ console.warn("Theme load failed", e); }
  let items = [];
  try{
    items = await loadJSON("./static/teams/purdue-mbb/items.json");
  }catch(e){
    console.warn("Items load failed", e);
    items = [{
      "type":"news",
      "title":"Waiting for first data sync…",
      "url":"#","summary":"Add static/teams/purdue-mbb/items.json or enable your GitHub Action to generate it.",
      "published_at": new Date().toISOString(),
      "source":"Team Hub","trust_level":"official"
    }];
  }
  render(items);
}

document.addEventListener("DOMContentLoaded", main);
