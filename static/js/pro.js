/* static/js/pro.js — Purdue MBB “Top 20 Headlines”
   - Fetches curated items.json
   - Renders up to 20 cards
   - Fills footer with build info
   - Mobile-first, dark theme
*/

(function () {
  // Basic DOM helpers
  const $ = (sel, el = document) => el.querySelector(sel);

  // Date formatting for cards
  function fmtDate(iso) {
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return '—';
    }
  }

  // Extract hostname for logo mapping
  function hostFromUrl(u) {
    try {
      return new URL(u).hostname;
    } catch {
      return '';
    }
  }

  // Map host -> local logo
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

    "watchstadium.com":       "static/logos/cbssports.svg",
    "theathletic.com":        "static/logos/cbssports.svg",
    "apnews.com":             "static/logos/cbssports.svg",
    "btn.com":                "static/logos/cbssports.svg"
  };

  function chooseThumb(link, image) {
    // prefer real image if feed provided one
    if (image && /^https?:\/\//i.test(image)) return image;
    // fallback to brand logo
    const h = hostFromUrl(link);
    if (h && LOGO_MAP[h]) return LOGO_MAP[h];
    // final fallback
    return 'static/placeholder-16x9.svg';
  }

  async function safeFetch(path) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return null;
    }
  }

  // year in footer
  const yearEl = $('#year');
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  // optional drawer/hamburger
  $('#hamburger')?.addEventListener('click', () => {
    $('#nav')?.classList.toggle('open');
  });

  // build footer state
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

  (async () => {
    // 1) load build meta
    buildData = await safeFetch('static/build.json');
    setBuildFooter();

    // 2) cache-bust param so we don't get stale JSON
    const ver = encodeURIComponent(buildData?.timestamp || String(Date.now()));
    const bust = (p) => `${p}?v=${ver}`;

    // 3) load curated items (collector writes this)
    const data = await safeFetch(bust('static/teams/purdue-mbb/items.json'));
    const list = Array.isArray(data?.items) ? data.items : [];

    // fix footer count if build.json still says 0
    if (list.length && (buildData?.items_count === 0 || buildData?.items_count === '0')) {
      setBuildFooter(list.length);
    }

    // 4) render cards
    renderHeadlines(list);

    // small diag info if you ever open diag.html
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

    // we only ever show up to 20
    items.slice(0, 20).forEach(it => {
      const card = document.createElement('a');
      card.className = 'card';
      card.href = it.link || '#';
      card.target = '_blank';
      card.rel = 'noopener noreferrer';

      // thumbnail/logo
      const img = document.createElement('img');
      img.className = 'thumb';
      img.loading = 'lazy';
      img.alt = '';
      img.src = chooseThumb(it.link, it.image);
      img.onerror = () => {
        img.onerror = null;
        img.src = 'static/placeholder-16x9.svg';
      };

      // text stack
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