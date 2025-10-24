(function(){
  const $ = (s,e=document)=>e.querySelector(s);
  const fmtDate = iso => {try{return new Date(iso).toLocaleDateString(undefined,{month:'short',day:'numeric'})}catch{return'—'}};
  const LOGO_MAP={
    "www.hammerandrails.com":"static/logos/hammerandrails.svg",
    "hammerandrails.com":"static/logos/hammerandrails.svg",
    "www.jconline.com":"static/logos/jconline.svg",
    "purdue.rivals.com":"static/logos/rivals.svg",
    "www.on3.com":"static/logos/on3.svg",
    "www.espn.com":"static/logos/espn.svg",
    "sports.yahoo.com":"static/logos/yahoo.svg",
    "www.cbssports.com":"static/logos/cbssports.svg",
    "www.youtube.com":"static/logos/youtube.svg",
    "youtu.be":"static/logos/youtube.svg"
  };
  const host=u=>{try{return new URL(u).hostname}catch{return""}};
  const chooseThumb=(link,img)=>{
    if(img&&/^https?:\/\//i.test(img))return img;
    const h=host(link);if(h&&LOGO_MAP[h])return LOGO_MAP[h];
    return"static/placeholder-16x9.svg";
  };
  $('#hamburger')?.addEventListener('click',()=>$('#nav')?.classList.toggle('open'));
  const y=$('#year');if(y)y.textContent=new Date().getFullYear();
  const safeFetch=async p=>{try{const r=await fetch(p,{cache:'no-store'});if(!r.ok)throw 0;return await r.json()}catch{return null}};
  let buildData=null;
  (async()=>{buildData=await safeFetch('static/build.json');const b=$('#build-line');if(b&&buildData)b.textContent=`Build: ${buildData.timestamp||'—'} • commit ${buildData.commit||'—'} • ${buildData.items_count??'—'} items`;})();
  Promise.all([
    safeFetch('static/teams/purdue-mbb/items.json'),
    safeFetch('static/schedule.json'),
    safeFetch('static/widgets.json'),
    safeFetch('static/sources.json')
  ]).then(([items,schedule,widgets,sources])=>{
    const list=Array.isArray(items?.items)?items.items:[];
    if(list.length&&buildData&&(buildData.items_count===0||buildData.items_count==='0'))$('#build-line').textContent=`Build: ${buildData.timestamp||'—'} • commit ${buildData.commit||'—'} • ${list.length} items`;
    const grid=$('#news-grid'),empty=$('#news-empty');
    if(list.length){empty?.classList.add('hidden');
      list.slice(0,10).forEach(it=>{
        const a=document.createElement('a');a.className='card';a.href=it.link||'#';a.target='_blank';
        const img=document.createElement('img');img.className='thumb';img.loading='lazy';img.src=chooseThumb(it.link,it.image);
        const meta=document.createElement('div');meta.className='meta';
        meta.innerHTML=`<div class="source">${it.source||''}</div><div class="title">${it.title||''}</div><div class="date">${fmtDate(it.date)}</div>`;
        a.append(img,meta);grid?.append(a);
      });
    }else empty?.classList.remove('hidden');
    const vrow=$('#video-row');const vids=list.filter(i=>(i.link||'').includes('youtube'));
    vids.slice(0,8).forEach(v=>{try{const u=new URL(v.link);let id=u.searchParams.get('v');if(!id&&u.hostname==='youtu.be')id=u.pathname.slice(1);
      if(!id)return;const wrap=document.createElement('div');wrap.className='card video';
      wrap.innerHTML=`<iframe width="100%" height="158" src="https://www.youtube.com/embed/${id}" frameborder="0" allowfullscreen></iframe><div class="meta"><div class="title">${v.title}</div><div class="date">${fmtDate(v.date)}</div></div>`;
      vrow?.append(wrap);}catch{}});
    const tbody=document.querySelector('#schedule .table tbody');
    (schedule?.games||[]).forEach(g=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${g.date}</td><td>${g.opponent}</td><td>${g.result||''}</td>`;tbody?.append(tr);});
    if(widgets){$('#ap-rank').textContent=widgets.ap_rank??'—';$('#kenpom-rank').textContent=widgets.kenpom_rank??'—';
      (widgets.nil||[]).forEach(r=>{const li=document.createElement('li');li.innerHTML=`<span class="name">${r.name}</span><span class="val">${r.valuation}</span>`;$('#nil-list')?.append(li);});}
    (sources?.items||[]).forEach(s=>{const li=document.createElement('li');li.innerHTML=`<a href="${s.url}" target="_blank">${s.name}</a>`;$('#sources-list')?.append(li);});
  });
})();