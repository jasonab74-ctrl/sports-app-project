async function getJSON(path){
  const r = await fetch(path, { cache: "no-store" });
  if(!r.ok) throw new Error("HTTP " + r.status + " for " + path);
  return await r.json();
}

function cardHTML(item){
  const dt = item.published_at ? new Date(item.published_at) : null;
  const when = dt ? dt.toLocaleString() : "";
  const img = item.image_url ? `<img src="${item.image_url}" alt="">` : "";
  return `
  <div class="card">
    ${img}
    <div>
      <a href="${item.url}" target="_blank"><strong>${item.title}</strong></a>
      <div class="meta">${item.source} • ${when}</div>
    </div>
  </div>`;
}

async function loadTeam(team){
  try{
    // IMPORTANT: relative path for project Pages
    const data = await getJSON(`static/teams/${team}/items.json`);
    const items = data.items || [];
    const daily = items.slice(0, 8);
    const feed = items.slice(0, 50);
    document.getElementById("daily").innerHTML = daily.map(cardHTML).join("");
    document.getElementById("feed").innerHTML = feed.map(cardHTML).join("");
  }catch(e){
    console.error(e);
    document.getElementById("daily").innerHTML = "<p>Nothing yet.</p>";
    document.getElementById("feed").innerHTML = "<p>Nothing yet.</p>";
  }
}

const teamSelect = document.getElementById("teamSelect");
document.getElementById("refreshBtn").addEventListener("click", () => loadTeam(teamSelect.value));
loadTeam(teamSelect.value);
