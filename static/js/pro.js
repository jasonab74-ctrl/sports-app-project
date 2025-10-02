(() => {
  const $ = (sel, ctx=document) => ctx.querySelector(sel);

  // Base path for GH Pages (e.g., /sports-app-project/)
  const PATH_BASE = (function(){
    const parts = location.pathname.split('/').filter(Boolean);
    return parts.length ? `/${parts[0]}/` : '/';
  })();
  const url = (p) => `${PATH_BASE}${p.replace(/^\//,'')}`;

  /* ---------- Utilities ---------- */
  function escapeHTML(s){ return (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }
  function ftimeAgo(date){
    try{
      const d=new Date(date); const diff=(Date.now()-d.getTime())/1000;
      if(diff<90) return 'just now';
      const units=[['y',31536000],['mo',2592000],['d',86400],['h',3600],['m',60]];
      for(const [l,s] of units){ const v=Math.floor(diff/s); if(v>=1) return `${v}${l} ago`; }
      return 'just now';
    }catch(e){return''}
  }
  function debug(msg){ const el=$('#debugMsg'); if(el) el.textContent=msg; console.log('[DEBUG]', msg); }

  /* ---------- IMAGE ACCURACY HEURISTICS ---------- */
  // Some feeds provide logos/placeholders or hotlink-protected images.
  // Heuristics:
  //  - Prefer YouTube thumbnails when link is YT.
  //  - Drop likely-bad filenames (logo, sprite, default, placeholder, blank).
  //  - If image host is a known CDN pattern but filename tiny (<= 20 chars) w/out extension, drop.
  //  - Always add referrerpolicy="no-referrer" to reduce 403 blocks.
  function isLikelyBadImage(src){
    if(!src) return true;
    const s = src.toLowerCase();
    if (/(sprite|logo|placeholder|default|blank|spacer)\./.test(s)) return true;
    if (!/\.(jpg|jpeg|png|webp|gif)(\?|$)/.test(s)) return true;
    try{
      const u = new URL(src);
      // Filenames like ".../img?id=123" are often trackers; let them pass only if host matches link later.
      const name = u.pathname.split('/').pop() || '';
      if (name.length <= 4) return true;
    }catch(_){}
    return false;
  }
  function ytId(urlStr){
    try{
      const u = new URL(urlStr);
      if (u.hostname.includes('youtu.be')) return u.pathname.slice(1);
      if (u.searchParams.get('v')) return u.searchParams.get('v');
      const m = /\/embed\/([^?]+)/.exec(u.pathname);
      if (m) return m[1];
      return null;
    }catch(_){ return null }
  }
  function initialsFrom(str=''){
    const parts=(str||'').split(/\s+/);
    const a=(parts[0]||'')[0]||''; const b=(parts[1]||'')[0]||'';
    return (a+b).toUpperCase() || '•';
  }
  function buildFallback(aspect,label){
    const cls = aspect==='16x9' ? 'fallback-16x9' : 'fallback-4x3';
    return `<div class="${cls}"><div class="fallback-badge">${escapeHTML(initialsFrom(label))}</div></div>`;
  }
  function safeImgTag(src, aspect, label){
    if (isLikelyBadImage(src)) return buildFallback(aspect, label);
    return `<img
      src="${src}"
      alt=""
      class="${aspect==='16x9'?'hero-img':'card-img'}"
      loading="${aspect==='16x9'?'eager':'lazy'}"
      decoding="async"
      referrerpolicy="no-referrer"
      crossorigin="anonymous"
      onerror="this.replaceWith((${buildFallback}).call(null,'${aspect}','${escapeHTML(label)}'))"
    >`;
  }

  /* ---------- UI helpers ---------- */
  function badge(tag){
    const t=(tag||'').toLowerCase();
    if (t.includes('official')) return `<span class="pill">official</span>`;
    if (t.includes('insider'))  return `<span class="pill">insider</span>`;
    if (t.includes('national')) return `<span class="pill">national</span>`;
    return t ? `<span class="pill">${escapeHTML(t)}</span>` : '';
  }

  /* ---------- Data loaders ---------- */
  async function getTeam(){
    try{
      const r = await fetch(url('static/team.json'), {cache:'no-cache'});
      if (r.ok){
        const j = await r.json();
        return j.slug || j.team?.slug || j.id || window.__TEAM_SLUG || 'purdue-mbb';
      }
    }catch(_){}
    return window.__TEAM_SLUG || 'purdue-mbb';
  }

  as
