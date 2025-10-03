(function(){
  function initialsFrom(str){
    const t = (str||'').trim().split(/\s+/);
    return (t[0]?.[0]||'') + (t[1]?.[0]||'') || '•';
  }

  function getOverrides(){
    try {
      const el = document.getElementById('image-overrides');
      if (!el) return {};
      return JSON.parse(el.textContent || '{}') || {};
    } catch { return {}; }
  }

  function hostFromLink(img){
    try {
      const a = img.closest('a');
      if (!a) return '';
      return new URL(a.href).hostname.toLowerCase();
    } catch { return ''; }
  }

  function swapToPosterOrFallback(img){
    const overrides = getOverrides();
    const host = hostFromLink(img);
    const poster = overrides[host] || null;

    const aspect = img.getAttribute('data-aspect') || '4x3';
    const label  = img.getAttribute('data-label') || '';

    if (poster) {
      // simple swap: keep <img>, change src to poster
      img.src = poster;
      img.removeAttribute('srcset'); // in case we add <picture> later
      img.onerror = null; // avoid loops
      return;
    }

    // Replace <img> with a fallback tile
    const wrap = document.createElement('div');
    wrap.className = `fallback-${aspect}`;
    const b = document.createElement('div');
    b.className = 'fallback-badge';
    b.textContent = initialsFrom(label);
    wrap.appendChild(b);
    img.replaceWith(wrap);
  }

  function attachImageGuards(){
    const imgs = document.querySelectorAll('img.hero-img, img.card-img');
    imgs.forEach(img => {
      // If the image fails for any reason, swap immediately
      img.addEventListener('error', () => swapToPosterOrFallback(img), { once: true });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachImageGuards);
  } else {
    attachImageGuards();
  }
})();