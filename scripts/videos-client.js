// scripts/videos-client.js
// Client-side renderer for Latest Videos from static/teams/purdue-mbb/items.json

(async function () {
  const grid = document.getElementById('videos-grid');
  const statusEl = document.getElementById('videos-status');

  function posterSVG(label1, label2 = "") {
    return `
      <svg class="poster" viewBox="0 0 1200 675" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${label1}">
        <rect width="1200" height="675" fill="#0d0f12"/>
        <rect x="64" y="64" width="1072" height="547" rx="18" ry="18" class="frame"/>
        <rect x="500" y="238" width="200" height="200" rx="24" fill="#1a1e26"/>
        <polygon points="560,270 560,406 660,338" fill="#f2c94c"/>
        <text x="600" y="480" text-anchor="middle" class="t2" font-size="28">${label2 || label1}</text>
      </svg>`;
  }
  const pill=(t)=>`<span class="pill">${t}</span>`;

  function cardHTML(item){
    const label2 = item.source?.includes('YouTube') ? 'YouTube' : (item.source || 'Video');
    return `
      <article class="card video-card">
        <a class="card-img-wrap" href="${item.link}" target="_blank" rel="noopener" aria-label="${item.title} (opens in new tab)">
          <div class="hero-art">${posterSVG('Video', label2)}</div>
        </a>
        <div class="card-body">
          <div class="pills">${item.tier?pill(item.tier):""}${item.source?pill(item.source):""}</div>
          <a class="card-title" href="${item.link}" target="_blank" rel="noopener">${item.title}</a>
        </div>
      </article>`;
  }

  try {
    const res = await fetch('static/teams/purdue-mbb/items.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const vids = (data.items || [])
      .filter(i => (i.type || '').toLowerCase() === 'video')
      .sort((a,b)=> (b.ts||0)-(a.ts||0))
      .slice(0, 6);

    if (!vids.length) {
      statusEl.textContent = "No new videos yet.";
      statusEl.hidden = false;
      return;
    }

    grid.innerHTML = vids.map(cardHTML).join('');
    statusEl.hidden = true;
  } catch (e) {
    console.warn(e);
    statusEl.textContent = "Unable to load videos.";
    statusEl.hidden = false;
  }
})();