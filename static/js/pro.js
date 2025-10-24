/* static/js/pro.js — Purdue MBB Hub (cache-busted JSON, safe thumbnails) */

(function () {
  // ---------- Helpers ----------
  const $  = (sel, el = document) => el.querySelector(sel);
  const fmtDate = (iso) => {
    try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }
    catch { return '—'; }
  };
  const hostFromUrl = (u) => { try { return new URL(u).hostname; } catch { return ''; } };

  // Source host -> local logo
  const LOGO_MAP = {
    "www.hammerandrails.com":"static/logos/hammerandrails.svg",
    "hammerandrails.com":"static/logos/hammerandrails.svg",
    "rssfeeds.jconline.com":"static/logos/jconline.svg",
    "www.jconline.com":"static/logos/jconline.svg",
    "purdue.rivals.com":"static/logos/rivals.svg",
    "www.on3.com":"static/logos/on3.svg",
    "www.espn.com":"static/logos/espn.svg",
    "sports.yahoo.com":"static/logos/yahoo.svg",
    "www.cbssports.com":"static/logos/cbssports.svg",
    "www.youtube.com":"static/logos/youtube.svg",
    "youtube.com":"static/logos/youtube.svg",
    "youtu.be":"static/logos/youtube.svg"
  };

  const chooseThumb = (link, image) => {
    if (image && /^https?:\/\//i.test(image)) return image;
    const h = hostFromUrl(link);
    if (h && LOGO_MAP[h]) return LOGO_MAP[h];
    return 'static/placeholder-16x9.svg';
  };

  const safeFetch = async (path) => {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) throw new Error(String(res.status));
      return await res.json();
    } catch { return null; }
  };

  // ---------- Header / nav ----------
  $('#hamburger')?.addEventListener('click', () => $('#nav')?.classList.toggle('open'));
  const year = $('#year'); if (year) year.textContent = new Date().getFullYear();

  // ---------- Build info (used for cache-busting) ----------
  let buildData = null;
  const setBuildLine = (itemsCountHint) => {
    const line = $('#build-line');
    if (!line) return;
    const ts = buildData?.timestamp || '—';
    const sha = buildData?.commit || '—';
    const count = (typeof itemsCountHint === 'number') ? itemsCountHint : (buildData?.items_count ?? '—');
    const when = (() => {
      try {
        const d = new Date(buildData?.timestamp || Date.now());
        const mins = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000));
        return ` • updated ${mins} min ago`;
      } catch { return ''; }
    })();
    line.textContent = `Build: ${ts} • commit ${sha} • ${count} items${when}`;
  };

  (async () => {
    buildData = await safeFetch('static/build.json');
    setBuildLine();
    // After we know build timestamp, load JSON with a cache-busting param.
    const ver = encodeURIComponent(buildData?.timestamp || String(Date.now()));
    const j = (p) => `${p}?v=${ver}`;

    Promise.all([
      safeFetch(j('static/teams/purdue-mbb/items.json')),
      safeFetch(j('static/schedule.json')),
      safeFetch(j('static/widgets.json')),
      safeFetch(j('static/sources.json'))
    ]).then(([items, schedule, widgets, sources]) => {
      const list = Array.isArray(items?.items) ? items.items : [];

      // If build.json said 0 but we have items, correct the footer display
      if (list.length && (buildData?.items_count === 0 || buildData?.items_count === '0')) {
        setBuildLine(list.length);
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
          img.onerror = () => { img.onerror = null; img.src = 'static/placeholder-16x9.svg'; };

          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.innerHTML = `
            <div class="source">${(it.source || '').toString()}</div>
            <div class="title">${(it.title  || '').toString()}</div>
            <div class="date">${fmtDate(it.date)}</div>
          `;

          a.append(img, meta);
          grid?.appendChild(a);
        });
      } else {
        empty?.classList.remove('hidden');
      }

      // ---------- Videos ----------
      const vrow = $('#video-row');
      if (vrow) {
        const vids = list.filter(i => {
          const L = (i.link || '').toLowerCase();
          return L.includes('youtube.com') || L.includes('youtu.be');
        });
        vids.slice(0,8).forEach(v=>{
          try{
            const u=new URL(v.link); let id=u.searchParams.get('v');
            if(!id && u.hostname==='youtu.be') id=u.pathname.slice(1);
            if(!id) return;
            const wrap=document.createElement('div'); wrap.className='card video';
            wrap.innerHTML = `
              <iframe width="100%" height="158" src="https://www.youtube.com/embed/${id}" frameborder="0" allowfullscreen loading="lazy"></iframe>
              <div class="meta"><div class="title">${v.title||''}</div><div class="date">${fmtDate(v.date)}</div></div>
            `;
            vrow.appendChild(wrap);
          }catch{}
        });
      }

      // ---------- Schedule ----------
      const tbody=document.querySelector('#schedule .table tbody');
      if (tbody) {
        (schedule?.games||[]).forEach(g=>{
          const tr=document.createElement('tr');
          tr.innerHTML=`<td>${g.date}</td><td>${g.opponent}</td><td>${g.result||''}</td>`;
          tbody.appendChild(tr);
        });
      }

      // ---------- Rankings + NIL ----------
      if (widgets) {
        const ap=$('#ap-rank'), kp=$('#kenpom-rank');
        if (ap) ap.textContent = widgets.ap_rank ?? '—';
        if (kp) kp.textContent = widgets.kenpom_rank ?? '—';
        (widgets.nil||[]).forEach(row=>{
          const li=document.createElement('li');
          li.innerHTML=`<span class="name">${row.name}</span><span class="val">${row.valuation}</span>`;
          $('#nil-list')?.appendChild(li);
        });
      }

      // ---------- Sources ----------
      (sources?.items||[]).forEach(s=>{
        const li=document.createElement('li');
        li.innerHTML=`<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.name}</a>`;
        $('#sources-list')?.appendChild(li);
      });
    });
  })();
})();