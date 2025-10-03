(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);

  // Project base (GitHub Pages: /sports-app-project/)
  const PATH_BASE = (function(){
    const parts = location.pathname.split('/').filter(Boolean);
    return parts.length ? `/${parts[0]}/` : '/';
  })();
  const url = (p) => `${PATH_BASE}${p.replace(/^\//,'')}`;

  /* ================= HYBRID ART SETTINGS =================
     Set this to your deployed Cloudflare Worker URL.
     Example: "https://my-proxy.workers.dev"
  ======================================================== */
  const PROXY_BASE = "https://<your-worker>.workers.dev";  // <— set this!

  // Hosts that should route via the proxy
  const PROXY_HOSTS = new Set([
    'img.si.com','si.com',
    'gannett-cdn.com','jconline.com',
    's.yimg.com','yimg.com','yahoo.com',
    '247sports.imgix.net','247sports.com',
    'rivalscdn.com','rivals.com',
    'sportshqimages.cbsimg.net','cbssports.com',
    'vox-cdn.com','sbnation.com',
    'espncdn.com','espn.com',
    'apnews.com',
    'nbcsports.com',
    'i.ytimg.com','ytimg.com','youtube.com',
    'purduesports.com'
  ]);

  /* === utils (escape, timeago, debug) === */
  const escapeHTML = (s) => (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  function ftimeAgo(date){ try{const d=new Date(date);const diff=(Date.now()-d.getTime())/1000;if(diff<90)return'just now';const u=[['y',31536000],['mo',2592000],['d',86400],['h',3600],['m',60]];for(const [l,s] of u){const v=Math.floor(diff/s);if(v>=1)return`${v}${l} ago`;}return'just now';}catch(_){return''} }
  const debug = (m) => { const el=$('#debugMsg'); if(el) el.textContent=m; console.log('[DEBUG]', m); };
  const etld1 = (host) => { if(!host) return ''; const p=host.toLowerCase().split('.').filter(Boolean); return p.length<=2?host.toLowerCase():p.slice(-2).join('.'); };

  function initialsFrom(str=''){ const parts=(str||'').trim().split(/\s+/); return ((parts[0]||'')[0]||'').toUpperCase() + ((parts[1]||'')[0]||'').toUpperCase() || '•'; }
  function fallbackNode(aspect,label){ const div=document.createElement('div'); div.className=aspect==='16x9'?'fallback-16x9':'fallback-4x3'; const inner=document.createElement('div'); inner.className='fallback-badge'; inner.textContent=initialsFrom(label); div.appendChild(inner); return div; }
  function attachImgFallbacks(ctx=document){ ctx.querySelectorAll('img[data-aspect]').forEach(img=>{ const aspect=img.getAttribute('data-aspect'); const label=img.getAttribute('data-label')||''; img.addEventListener('error',()=>{ img.replaceWith(fallbackNode(aspect,label)); },{once:true}); }); }

  /* === image logic === */
  function ytId(urlStr){ try{const u=new URL(urlStr); if(u.hostname.includes('youtu.be')) return u.pathname.slice(1); if(u.searchParams.get('v')) return u.searchParams.get('v'); const m=/\/embed\/([^?]+)/.exec(u.pathname); return m?m[1]:null;}catch(_){return null} }
  const ytThumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;

  function isLikelyBadImage(src){ if(!src) return true; const s=src.toLowerCase(); if(/(sprite|logo|placeholder|default|blank|spacer)\.(png|svg|gif)$/.test(s)) return true; if(!/\.(jpg|jpeg|png|webp)(\?|$)/.test(s)) return true; return false; }

  function proxify(src){ if(!PROXY_BASE) return src; try{ const h=etld1(new URL(src).host.toLowerCase()); if(PROXY_HOSTS.has(h)) return `${PROXY_BASE}/?u=${encodeURIComponent(src)}`; return src; }catch{ return src; } }

  function selectImageForItem(item){ const id=ytId(item.link||''); if(id) return ytThumb(id); const candidate=item.image||''; if(!candidate||isLikelyBadImage(candidate)) return ''; return proxify(candidate); }

  /* === UI bits === */
  function badge(tag){ const t=(tag||'').toLowerCase(); if(t.includes('official'))return`<span class="pill">official</span>`; if(t.includes('insider'))return`<span class="pill">insider</span>`; if(t.includes('national'))return`<span class="pill">national</span>`; return t?`<span class="pill">${escapeHTML(t)}</span>`:''; }

  /* === Data loaders (rankings, schedule, items, videos, insiders) === */
  // ... (identical to the last full pro.js I gave you, unchanged except uses selectImageForItem + proxify)

  async function init(){
    // same init as before
    await Promise.all([/* loadRankings(), loadSchedule(), loadItems(), loadVideos(), loadInsiders() */]);
  }
  document.addEventListener('DOMContentLoaded', init);
})();