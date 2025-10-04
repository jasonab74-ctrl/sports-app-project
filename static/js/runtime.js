(function () {
  function initialsFrom(str) {
    const t = (str || '').trim().split(/\s+/);
    return (t[0]?.[0] || '') + (t[1]?.[0] || '') || '•';
  }
  function getOverrides() {
    try { const el = document.getElementById('image-overrides'); return el ? JSON.parse(el.textContent || '{}') || {} : {}; }
    catch { return {}; }
  }
  function hostFromLink(img) {
    try { const a = img.closest('a'); return a ? new URL(a.href).hostname.toLowerCase() : ''; }
    catch { return ''; }
  }
  function getParam(name, def) {
    const u = new URL(location.href);
    return u.searchParams.get(name) || def;
  }
  function setParam(name, value) {
    const u = new URL(location.href);
    if (value === null || value === 'all') u.searchParams.delete(name);
    else u.searchParams.set(name, value);
    history.replaceState({}, '', u.toString());
  }
  /* Image fail-safe */
  function swapToPosterOrFallback(img) {
    const overrides = getOverrides();
    const host = hostFromLink(img);
    const poster = overrides[host] || null;
    const aspect = img.getAttribute('data-aspect') || '4x3';
    const label = img.getAttribute('data-label') || '';
    if (poster) {
      img.onerror = null; img.removeAttribute('srcset'); img.src = poster; return;
    }
    const wrap = document.createElement('div'); wrap.className = `fallback-${aspect}`;
    const b = document.createElement('div'); b.className = 'fallback-badge'; b.textContent = initialsFrom(label);
    wrap.appendChild(b); img.replaceWith(wrap);
  }
  function attachImageGuards() {
    document.querySelectorAll('img.hero-img, img.card-img').forEach(img => {
      img.addEventListener('error', () => swapToPosterOrFallback(img), { once: true });
    });
  }
  /* Filters