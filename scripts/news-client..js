// scripts/news-client.js
// Live headlines renderer from static/teams/purdue-mbb/items.json
(async function () {
  const grid = document.getElementById('news-grid');
  const heroWrap = document.getElementById('news-hero');
  const heroMeta = document.getElementById('news-hero-meta');
  const statusEl = document.getElementById('news-status');

  function posterSVG(label1, label2 = "") {
    return `
      <svg class="poster" viewBox="0 0 1200 900" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${label1}">
        <rect width="1200" height="900" fill="#0d0f12"/>
        <rect x="64" y="64" width="1072" height="772" rx="18" class="frame"/>
        <text x="600" y="${label2 ? 430 : 460}" text-anchor="middle" class="t1" font-size="${label2 ? 110 : 120}">${label1}</text>
        ${label2 ? `<text x="600" y="500" text-anchor="middle" class="t2" font-size="34">${label2}</text>` : ""}
      </svg>`;
  }

  function sourceLabels(source) {
    const map = {
      "PurdueSports.com": ["PurdueSports.com", "Official"],
      "Sports Illustrated CBB": ["Sports Illustrated", "CBB"],
      "CBS Sports CBB": ["CBS Sports", "CBB"],
      "Yahoo CBB": ["Yahoo Sports", "CBB"],
      "Journal & Courier": ["Journal & Courier", "Local"],
      "247Sports Purdue": ["247Sports", "Purdue"],
      "Gold and Black (Rivals)": ["Rivals", "Gold & Black"],
      "YouTube": ["YouTube", ""]
    };
    return map[source] || [source, ""];
  }

  const pill = (t) => `<span class="pill">${t}</span>`;

  function cardHTML(item) {
    const [l1, l2] = sourceLabels(item.source || "Source");
    return `
      <article class="card" data-tier="${item.tier || 'national'}">
        <a class="card-img-wrap" href="${item.link}" target="_blank" rel="noopener">
          <div class="card-art">${posterSVG(l1, l2)}</div>
        </a>
        <div class="card-body">
          <div class="pills">${item.tier ? pill(item.tier) : ""}${item.source ? pill(item.source) : ""}</div>
          <a class="card-title" href="${item.link}" target="_blank" rel="noopener">${item.title}</a>
        </div>
      </article>`;
  }

  function heroHTML(item) {
    const [l1, l2] = sourceLabels(item.source || "Source");
    return `
      <a class="hero-img-wrap" href="${item.link}" target="_blank" rel="noopener">
        <div class="hero-art">${posterSVG(l1, l2)}</div>
      </a>`;
  }

  try {
    const res = await fetch('static/teams/purdue-mbb/items.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = (data.items || []).sort((a,b)=> (b.ts||0)-(a.ts||0));

    if (!items.length) {
      statusEl.textContent = "No live headlines right now.";
      statusEl.hidden = false;
      return;
    }

    const heroIdx = Math.max(0, items.findIndex(i => (i.type||'article') !== 'video'));
    const heroItem = items[heroIdx] || items[0];
    const gridItems = items.filter((_,i)=> i !== heroIdx);

    heroWrap.innerHTML = heroHTML(heroItem);
    heroMeta.innerHTML = `
      <div class="pills">${heroItem.tier?pill(heroItem.tier):""}${heroItem.source?pill(heroItem.source):""}</div>
      <h3 class="hero-title"><a href="${heroItem.link}" target="_blank" rel="noopener">${heroItem.title}</a></h3>
    `;
    grid.innerHTML = gridItems.slice(0,9).map(cardHTML).join('');
    statusEl.hidden = true;
  } catch (err) {
    console.warn(err);
    statusEl.textContent = "Unable to load live headlines.";
    statusEl.hidden = false;
  }
})();