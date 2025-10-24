(function(){
  const $ = (sel, el=document) => el.querySelector(sel);
  const fmtDate = (iso) => {
    try { return new Date(iso).toLocaleDateString(undefined,{month:'short',day:'numeric'}); }
    catch { return '—'; }
  };
  const hostIcon = (url) => {
    try { return `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=128`; }
    catch { return 'static/placeholder-16x9.svg'; }
  };

  // Mobile nav + year
  $('#hamburger')?.addEventListener('click', () => $('#nav')?.classList.toggle('open'));
  const y=$('#year'); if (y) y.textContent=new Date().getFullYear();

  const safeFetch = async (path) => {
    try{ const res=await fetch(path,{cache:'no-store'}); if(!res.ok) throw new Error(res.status); return await res.json(); }
    catch{ return null; }
  };

  // Preload build info
  let buildData=null;
  (async () => {
    buildData = await safeFetch('static/build.json');
    const line = $('#build-line');
    if (line && buildData) {
      line.textContent = `Build: ${buildData.timestamp||'—'} • commit ${buildData.commit||'—'} • ${buildData.items_count ?? '—'} items`;
    }
  })();

  // Load app data
  Promise.all([
    safeFetch('static/teams/purdue-mbb/items.json'),
    safeFetch('static/schedule.json'),
    safeFetch('static/widgets.json'),
    safeFetch('static/sources.json')
  ]).then(([items, schedule, widgets, sources]) => {
    const list = Array.isArray(items?.items) ? items.items : [];

    // If build.json said 0 but we have data, fix the footer display
    if (list.length && buildData && (buildData.items_count === 0 || buildData.items_count === '0')) {
      const line = $('#build-line');
      if (line) line.textContent = `Build: ${buildData.timestamp||'—'} • commit ${buildData.commit||'—'} • ${list.length} items`;
    }

    // Headlines
    const grid = $('#news-grid'), empty = $('#news-empty');
    if (list.length) {
      empty?.classList.add('hidden');
      list.slice(0, 10).forEach(it => {
        const a = document.createElement('a');
        a.className = 'card';
        a.href = it.link || '#';
        a.target = '_blank'; a.rel = 'noopener noreferrer';

        const img = document.createElement('img');
        img.className = 'thumb';
        img.loading = 'lazy';
        img.src = it.image || hostIcon(it.link);

        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.innerHTML = `
          <div class="source">${(it.source||'').toString()}</div>
          <div class="title">${(it.title||'').toString()}</div>
          <div class="date">${fmtDate(it.date)}</div>
        `;

        a.appendChild(img); a.appendChild(meta);
        grid?.appendChild(a);
      });
    } else {
      empty?.classList.remove('hidden');
    }

    // Videos: from YouTube links in list
    const vrow = $('#video-row');
    const vids = list.filter(i => (i.link||'').includes('youtube.com') || (i.link||'').includes('youtu.be'));
    vids.slice(0,8).forEach(v=>{
      try{
        const u=new URL(v.link); let id=u.searchParams.get('v');
        if(!id && u.hostname==='youtu.be') id=u.pathname.slice(1);
        if(!id) return;
        const wrap=document.createElement('div'); wrap.className='card video';
        wrap.innerHTML = `
          <iframe width="100%" height="158" src="https://www.youtube.com/embed/${id}" frameborder="0" allowfullscreen loading="lazy"></iframe>
          <div class="meta"><div class="title">${v.title}</div><div class="date">${fmtDate(v.date)}</div></div>
        `;
        vrow?.appendChild(wrap);
      }catch{}
    });

    // Schedule
    const tbody = document.querySelector('#schedule .table tbody');
    (schedule?.games||[]).forEach(g=>{
      const tr=document.createElement('tr');
      tr.innerHTML=`<td>${g.date}</td><td>${g.opponent}</td><td>${g.result||''}</td>`;
      tbody?.appendChild(tr);
    });

    // Rankings + NIL
    if (widgets) {
      $('#ap-rank')?.append(document.createTextNode(widgets.ap_rank ?? '—'));
      $('#kenpom-rank')?.append(document.createTextNode(widgets.kenpom_rank ?? '—'));
      (widgets.nil||[]).forEach(row=>{
        const li=document.createElement('li');
        li.innerHTML = `<span class="name">${row.name}</span><span class="val">${row.valuation}</span>`;
        $('#nil-list')?.appendChild(li);
      });
    }

    // Sources
    (sources?.items||[]).forEach(s=>{
      const li=document.createElement('li');
      li.innerHTML=`<a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.name}</a>`;
      $('#sources-list')?.appendChild(li);
    });
  });
})();