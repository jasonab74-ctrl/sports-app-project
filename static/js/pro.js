/* static/js/pro.js — Purdue MBB Hub (dark-gray/gold)
   - Forced thumbnails (logo-first, then placeholder)
   - iOS/Safari safe: no external favicon fetches
   - Robust build footer + widgets + videos + schedule
*/

(function () {
  // ---------- Helpers ----------
  const $  = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

  const fmtDate = (iso) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch { return '—'; }
  };

  const hostFromUrl = (u) => {
    try { return new URL(u).hostname; } catch { return ''; }
  };

  // Map article link host -> local logo asset (drop these files in /static/logos/)
  const LOGO_MAP = {
    // Beat / local
    "www.hammerandrails.com": "static/logos/hammerandrails.svg",
    "hammerandrails.com":     "static/logos/hammerandrails.svg",
    "rssfeeds.jconline.com":  "static/logos/jconline.svg",
    "www.jconline.com":       "static/logos/jconline.svg",
    "purdue.rivals.com":      "static/logos/rivals.svg",
    "purdue.rivals.com:443":  "static/logos/rivals.svg",

    // National
    "www.on3.com":            "static/logos/on3.svg",
    "www.espn.com":           "static/logos/espn.svg",
    "sports.yahoo.com":       "static/logos/yahoo.svg",
    "www.cbssports.com":      "static/logos/cbssports.svg",

    // Video
    "www.youtube.com":        "static/logos/youtube.svg",
    "youtube.com":            "static/logos/youtube.svg",
    "youtu.be":               "static/logos/youtube.svg"
  };

  // Choose a thumbnail for a card (no external favicon fetches)
  const chooseThumb = (link, image) => {
    // 1) If feed provided a direct image URL, prefer it
    if (image && /^https?:\/\//i.test(image)) return image;
    // 2) Known logo per host
    const h = hostFromUrl(link);
    if (h && LOGO_MAP[h]) return LOGO_MAP[h];
    // 3) Final fallback
    return 'static/placeholder-16x9.svg';
  };

  // Fetch JSON safely without blowing up the UI
  const safeFetch = async (path) => {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) throw new Error(res.status);
      return await res.json();
    } catch {
      return null;
    }
  };

  // ---------- UI Basics ----------
  $('#hamburger')?.addEventListener('click', () => {
    $('#nav')?.classList.toggle('open');
  });

  const year = $('#year');
  if (year) year.textContent = new Date().getFullYear();

  // ---------- Footer build line (and lag fix) ----------
  let buildData = null;
  (async () => {
    buildData = await safeFetch('static/build.json');
    const line = $('#build-line');
    if (line && buildData) {
      line.textContent = `Build: ${buildData.timestamp || '—'} • commit ${buildData.commit || '—'} • ${buildData.items_count ?? '—'} items`;
    }
  })();

  // ---------- Main load ----------
  Promise.all([
    safeFetch('static/teams/purdue-mbb/items.json'), // headlines
    safeFetch('static/schedule.json'),
    safeFetch('static/widgets.json'),
    safeFetch('static/sources.json'),
  ]).then(([items, schedule, widgets, sources]) => {
    const list = Array.isArray(items?.items) ? items.items : [];

    // If build.json said "0" but we have items, correct the footer display
    if (list.length && buildData && (buildData.items_count === 0 || buildData.items_count === '0')) {
      const line = $('#build-line');
      if (line) {
        line.textContent = `Build: ${buildData.timestamp || '—'} • commit ${buildData.commit || '—'} • ${list.length} items`;
      }
    }

    // ---------- Headlines ----------
    const grid  = $('#news-grid');
    const empty = $('#news-empty');

    if (list.length) {
      empty?.classList.add('hidden');

      list.slice(0, 10).forEach((it) => {
        const a = document.createElement('a');
        a.className = 'card';
        a.href = it.link || '#';
        a.target = '_blank';
        a.rel = 'noopener noreferrer';

        const img = document.createElement('img');
        img.className = 'thumb';
        img.loading = 'lazy';
        img.alt = '';
        img.src = chooseThumb(it.link, it.image);

        // Final runtime safety: if a logo path is missing/renamed, show placeholder (no blue "?")
        img.onerror = () => { img.onerror = null; img.src = 'static/placeholder-16x9.svg'; };

        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.innerHTML = `
          <div class="source">${(it.source || '').toString()}</div>
          <div class="title">${(it.title  || '').toString()}</div>
          <div class="date">${fmtDate(it.date)}</div>
        `;

        a.appendChild(img);
        a.appendChild(meta);
        grid?.appendChild(a);
      });
    } else {
      empty?.classList.remove('hidden');
    }

    // ---------- Videos (from YouTube links in items) ----------
    const vrow = $('#video-row');
    if (vrow) {
      const vids = list.filter(i => {
        const L = (i.link || '').toLowerCase();
        return L.includes('youtube.com') || L.includes('youtu.be');
      });

      vids.slice(0, 8).forEach(v => {
        try {
          const u  = new URL(v.link);
          let id   = u.searchParams.get('v');
          if (!id && u.hostname === 'youtu.be') id = u.pathname.slice(1);
          if (!id) return;

          const wrap = document.createElement('div');
          wrap.className = 'card video';
          wrap.innerHTML = `
            <iframe width="100%" height="158"
              src="https://www.youtube.com/embed/${id}"
              frameborder="0" allowfullscreen loading="lazy"></iframe>
            <div class="meta">
              <div class="title">${v.title || ''}</div>
              <div class="date">${fmtDate(v.date)}</div>
            </div>
          `;
          vrow.appendChild(wrap);
        } catch { /* ignore parse errors */ }
      });
    }

    // ---------- Schedule ----------
    const tbody = document.querySelector('#schedule .table tbody');
    if (tbody) {
      (schedule?.games || []).forEach(g => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${g.date}</td><td>${g.opponent}</td><td>${g.result || ''}</td>`;
        tbody.appendChild(tr);
      });
    }

    // ---------- Rankings (raw numbers) + NIL ----------
    if (widgets) {
      const ap   = $('#ap-rank');
      const kp   = $('#kenpom-rank');
      if (ap) ap.textContent = widgets.ap_rank   ?? '—';
      if (kp) kp.textContent = widgets.kenpom_rank ?? '—';

      (widgets.nil || []).forEach(row => {
        const li = document.createElement('li');
        li.innerHTML = `<span class="name">${row.name}</span><span class="val">${row.valuation}</span>`;
        $('#nil-list')?.appendChild(li);
      });
    }

    // ---------- Key Sources ----------
    (sources?.items || []).forEach(s => {
      const li = document.createElement('li');
      li.innerHTML = `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.name}</a>`;
      $('#sources-list')?.appendChild(li);
    });
  });
})();