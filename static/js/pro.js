(function(){
  const $ = (sel, el=document) => el.querySelector(sel);
  const $$ = (sel, el=document) => Array.from(el.querySelectorAll(sel));
  const fmtDate = (iso) => {
    try {
      const d = new Date(iso);
      const opts = {month:'short', day:'numeric'};
      return d.toLocaleDateString(undefined, opts);
    } catch { return '—'; }
  };

  // Mobile nav
  const openNav = () => { $('#nav')?.classList.toggle('open'); };
  $('#hamburger')?.addEventListener('click', openNav);
  const y = $('#year'); if (y) y.textContent = new Date().getFullYear();

  const safeFetch = async (path) => {
    try{
      const res = await fetch(path, {cache:'no-store'});
      if(!res.ok) throw new Error(res.status);
      return await res.json();
    }catch(e){
      return { __error: String(e) };
    }
  };

  // Build stamp
  (async () => {
    const build = await safeFetch('static/build.json');
    const line = $('#build-line');
    if (line && build && !build.__error) {
      const ts = build.timestamp || '—';
      const sha = build.commit || '—';
      const cnt = (build.items_count ?? '—');
      line.textContent = `Build: ${ts} • commit ${sha} • ${cnt} items`;
    }
  })();

  // Load data
  Promise.all([
    safeFetch('static/teams/purdue-mbb/items.json'),
    safeFetch('static/schedule.json'),
    safeFetch('static/widgets.json'),
    safeFetch('static/sources.json')
  ]).then(([items, schedule, widgets, sources]) => {
    // Headlines
    const list = (items && items.items ? items.items : []);
    const grid = $('#news-grid');
    const empty = $('#news-empty');
    if (grid && empty) {
      if(list.length){
        empty.classList.add('hidden');
        list.slice(0, 10).forEach(it => {
          const a = document.createElement('a');
          a.className = 'card';
          a.href = it.link || '#';
          a.target = '_blank';
          a.rel = 'noopener noreferrer';

          const img = document.createElement('img');
          img.className = 'thumb';
          img.loading = 'lazy';
          img.src = it.image || 'static/placeholder-16x9.svg';
          img.alt = '';

          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.innerHTML = `
            <div class="source">${(it.source||'').toString()}</div>
            <div class="title">${(it.title||'').toString()}</div>
            <div class="date">${fmtDate(it.date)}</div>
          `;
          a.appendChild(img);
          a.appendChild(meta);
          grid.appendChild(a);
        });
      } else {
        empty.classList.remove('hidden');
      }
    }

    // Videos
    const vrow = $('#video-row');
    if (vrow) {
      const vids = (list || []).filter(i => (i.link||'').includes('youtube.com') || (i.link||'').includes('youtu.be'));
      vids.slice(0, 8).forEach(v => {
        try {
          const url = new URL(v.link);
          let id = url.searchParams.get('v');
          if(!id && url.hostname === 'youtu.be'){ id = url.pathname.slice(1); }
          if(!id) return;
          const wrap = document.createElement('div');
          wrap.className = 'card video';
          wrap.innerHTML = `
            <iframe width="100%" height="158" src="https://www.youtube.com/embed/${id}" frameborder="0" allowfullscreen loading="lazy"></iframe>
            <div class="meta"><div class="title">${v.title}</div><div class="date">${fmtDate(v.date)}</div></div>
          `;
          vrow.appendChild(wrap);
        } catch {}
      });
    }

    // Schedule
    const tbody = document.querySelector('#schedule .table tbody');
    if (tbody) {
      (schedule?.games || []).forEach(g => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${g.date}</td><td>${g.opponent}</td><td>${g.result || ''}</td>`;
        tbody.appendChild(tr);
      });
    }

    // Widgets
    if (widgets) {
      const ap = $('#ap-rank'), kp = $('#kenpom-rank');
      if (ap) ap.textContent = widgets.ap_rank ?? '—';
      if (kp) kp.textContent = widgets.kenpom_rank ?? '—';
      (widgets.nil || []).forEach(row => {
        const li = document.createElement('li');
        li.innerHTML = `<span class="name">${row.name}</span><span class="val">${row.valuation}</span>`;
        const ul = $('#nil-list');
        if (ul) ul.appendChild(li);
      });
    }

    // Sources
    (sources?.items || []).forEach(s => {
      const li = document.createElement('li');
      li.innerHTML = `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.name}</a>`;
      const ul = $('#sources-list');
      if (ul) ul.appendChild(li);
    });
  });
})();