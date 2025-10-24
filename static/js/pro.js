/* static/js/pro.js — Purdue MBB “Top 20 Headlines” Hub
   - Fetches items.json from static/teams/purdue-mbb/
   - Renders top 20 cards in #news-grid
   - Shows timestamp/commit/items count in footer
   - Local logos/placeholder for thumbnails
   - Mobile-first
*/

(function () {
  // ---------- Tiny DOM helpers ----------
  const $  = (sel, el = document) => el.querySelector(sel);

  const fmtDate = (iso) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return '—';
    }
  };

  const hostFromUrl = (u) => {
    try {
      return new URL(u).hostname;
    } catch {
      return '';
    }
  };

  // Map domains -> local logos. All of these should exist under /static/logos/
  const LOGO_MAP = {
    "www.hammerandrails.com": "static/logos/hammerandrails.svg",
    "hammerandrails.com":     "static/logos/hammerandrails.svg",

    "rssfeeds.jconline.com":  "static/logos/jconline.svg",
    "www.jconline.com":       "static/logos/jconline.svg",
    "jconline.com":           "static/logos/jconline.svg",

    "purdue.rivals.com":      "static/logos/rivals.svg",
    "purdue.rivals.com:443":  "static/logos/rivals.svg",
    "goldandblack.com":       "static/logos/rivals.svg",

    "www.on3.com":            "static/logos/on3.svg",
    "on3.com":                "static/logos/on3.svg",

    "www.espn.com":           "static/logos/espn.svg",
    "espn.com":               "static/logos/espn.svg",

    "sports.yahoo.com":       "static/logos/yahoo.svg",
    "www.cbssports.com":      "static/logos/cbssports.svg",
    "cbssports.com":          "static/logos/cbssports.svg",

    "www.youtube.com":        "static/logos/youtube.svg",
    "youtube.com":            "static/logos/youtube.svg",
    "youtu.be":               "static/logos/youtube.svg",

    "watchstadium.com":       "static/logos/cbssports.svg", // reuse or add stadium.svg later
    "theathletic.com":        "static/logos/cbssports.svg", // placeholder
    "apnews.com":             "static/logos/cbssports.svg", // placeholder
    "btn.com":                "static/logos/cbssports.svg"  // placeholder
  };

  // pick a thumbnail for an article card
  function chooseThumb(link, image) {
    // 1) If the feed gave us a real image URL, try it
    if (image && /^https?:\/\//i.test(image)) return image;

    // 2) otherwise, try a brand logo based on domain
    const h = hostFromUrl(link);
    if (h && LOGO_MAP[h]) return LOGO_MAP[h];

    // 3) fallback placeholder
    return 'static/placeholder-16x9.svg';
  }

  // fetch JSON with no caching
  async function safeFetch(path) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return null;
    }
  }

  // footer year
  const yearEl = $('#year');
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  // hamburger menu (mobile drawer if you keep it in HTML; safe no-op otherwise)
  $('#hamburger')?.addEventListener('click', () => {
    $('#nav')?.classList.toggle('open');
  });

  // ---- Build footer handling ----
  let buildData = null;

  function setBuildFooter(itemsCountMaybe) {
    const line = $('#build-line');
    if (!line) return;

    const ts  = buildData?.timestamp || '—';
    const sha = buildData?.commit    || '—';

    const cnt = (typeof itemsCountMaybe === 'number')
      ? itemsCountMaybe
      : (buildData?.items_count ?? '—');

    // "updated X min ago"
    let freshness = '';
    try {
      const then = new Date(buildData?.timestamp || Date.now());
      const mins = Math.max(0, Math.round((Date.now() - then.getTime()) / 60000));
      freshness = ` • updated ${mins} min ago`;
    } catch {
      // ignore
    }

    line.textContent = `Build: ${ts} • commit ${sha} • ${cnt} items${freshness}`;
  }

  // ---- Main load pipeline ----
  (async () => {
    // load build.json first (for footer + cache bust param)
    buildData = await safeFetch('static/build.json');
    setBuildFooter();

    // bust cache using build timestamp
    const ver = encodeURIComponent(buildData?.timestamp || String(Date.now()));
    const bust = (p) => `${p}?v=${ver}`;

    // load the 20 curated items
    const itemsJson = await safeFetch(bust('static/teams/purdue-mbb/items.json'));

    const list = Array.isArray(itemsJson?.items) ? itemsJson.items : [];

    // if build.json said "0" but we actually have items, fix footer
    if (list.length && (buildData?.items_count === 0 || buildData?.items_count === '0')) {
      setBuildFooter(list.length);
    }

    // render list
    renderHeadlines(list);

    // expose diag info for /diag.html (optional)
    window.__HUB_STATE__ = {
      build: buildData || null,
      total: list.length,
      newest: list[0]?.date || null
    };
  })();

  function renderHeadlines(items) {
    const grid  = $('#news-grid');
    const empty = $('#news-empty');
    if (!grid) return;

    if (!items.length) {
      empty?.classList.remove('hidden');
      return;
    }

    empty?.classList.add('hidden');

    // top 20 only (collector is already clipped to 20, but guard anyway)
    items.slice(0, 20).forEach(it => {
      const card = document.createElement('a');
      card.className = 'card';
      card.href = it.link || '#';
      card.target = '_blank';
      card.rel = 'noopener noreferrer';

      // thumb
      const img = document.createElement('img');
      img.className = 'thumb';
      img.loading = 'lazy';
      img.alt = '';
      img.src = chooseThumb(it.link, it.image);
      img.onerror = () => {
        img.onerror = null;
        img.src = 'static/placeholder-16x9.svg';
      };

      // meta block
      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.innerHTML = `
        <div class="source">${(it.source || '').toString()}</div>
        <div class="title">${(it.title  || '').toString()}</div>
        <div class="date">${fmtDate(it.date)}</div>
      `;

      card.appendChild(img);
      card.appendChild(meta);
      grid.appendChild(card);
    });
  }
})();