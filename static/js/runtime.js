// Minimal runtime: replace broken images with branded initials tiles
(function(){
  function initialsFrom(str=''){ const p=(str||'').trim().split(/\s+/); const a=(p[0]||'')[0]||''; const b=(p[1]||'')[0]||''; return (a+b).toUpperCase() || '•'; }
  function fallbackNode(aspect,label){ const div=document.createElement('div'); div.className=aspect==='16x9'?'fallback-16x9':'fallback-4x3'; const inner=document.createElement('div'); inner.className='fallback-badge'; inner.textContent=initialsFrom(label); div.appendChild(inner); return div; }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('img[data-aspect]').forEach(img=>{
      const aspect=img.getAttribute('data-aspect');
      const label=img.getAttribute('data-label')||'';
      img.addEventListener('error', ()=>{ img.replaceWith(fallbackNode(aspect,label)); }, { once:true });
    });
  });
})();