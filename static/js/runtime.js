(function(){
  function initialsFrom(str=''){ const p=(str||'').trim().split(/\s+/); return (p[0]?.[0]||'')+(p[1]?.[0]||'')||'•'; }
  function fallbackNode(aspect,label){
    const div=document.createElement('div');
    div.className=aspect==='16x9'?'fallback-16x9':'fallback-4x3';
    const inner=document.createElement('div'); inner.className='fallback-badge'; inner.textContent=initialsFrom(label);
    div.appendChild(inner); return div;
  }
  document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('img[data-aspect]').forEach(img=>{
      const aspect=img.dataset.aspect; const label=img.dataset.label||'';
      img.addEventListener('error',()=>{img.replaceWith(fallbackNode(aspect,label));},{once:true});
    });
  });
})();