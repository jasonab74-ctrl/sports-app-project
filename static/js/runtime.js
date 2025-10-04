(function () {
  /* ---------- Utilities ---------- */
  function initialsFrom(str) {
    const t = (str || '').trim().split(/\s+/);
    return (t[0]?.[0] || '') + (t[1]?.[0] || '') || '•';
  }

  function getOverrides() {
    try {
      const el = document.getElementById('image-overrides');
      if (!el) return {};
      return JSON.parse(el.textContent || '{}') || {};
    } catch { return {}; }
  }

  function hostFromLink(img) {
    try { const a = img.closest('a'); if (!a) return ''; return new URL(a.href).hostname.toLowerCase(); }
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

  /* ---------- Image fail-safe ---------- */
  function swapToPosterOrFallback(img) {
    const overrides = getOverrides();
    const host = hostFromLink(img);
    const poster = overrides[host] || null;

    const aspect = img.getAttribute('data-aspect') || '4x3';
    const label = img.getAttribute('data-label') || '';

    if (poster) {
      img.onerror = null;
      img.removeAttribute('srcset');
      img.src = poster;
      return;
    }
    const wrap = document.createElement('div');
    wrap.className = `fallback-${aspect}`;
    const b = document.createElement('div');
    b.className = 'fallback-badge';
    b.textContent = initialsFrom(label);
    wrap.appendChild(b);
    img.replaceWith(wrap);
  }

  function attachImageGuards() {
    document.querySelectorAll('img.hero-img, img.card-img').forEach((img) => {
      img.addEventListener('error', () => swapToPosterOrFallback(img), { once: true });
    });
  }

  /* ---------- Filters (chips) with URL sync ---------- */
  function initFilters() {
    const bar = document.querySelector('.panel-hd .chips[data-filter-ready]');
    const grid = document.getElementById('news-grid');
    if (!bar || !grid) return;

    const chips = Array.from(bar.querySelectorAll('.chip'));
    const cards = Array.from(grid.querySelectorAll('.card'));

    function apply(filter) {
      const f = ['official','insiders','national'].includes(filter) ? filter : 'all';
      cards.forEach((card) => {
        const tier = card.getAttribute('data-tier') || 'all';
        card.style.display = (f === 'all' ? true : (tier === f)) ? '' : 'none';
      });
      chips.forEach((c) => {
        const active = (c.getAttribute('data-filter') || 'all') === f;
        c.classList.toggle('is-active', active);
        c.setAttribute('aria-pressed', String(active));
      });
      setParam('filter', f === 'all' ? null : f);
    }

    bar.addEventListener('click', (e) => {
      const btn = e.target.closest('.chip');
      if (!btn) return;
      apply(btn.getAttribute('data-filter') || 'all');
    });

    // Apply initial state from URL
    apply(getParam('filter', 'all'));
  }

  /* ---------- Micro CSS polish ---------- */
  function injectStyle() {
    const css = `
      .chip:focus-visible { outline:2px solid #f2c94c; outline-offset:2px; }
      .hero .hero-img-wrap { margin-bottom: 8px; }
      .schedule-list .game { transition: transform .12s ease, background-color .12s ease, box-shadow .12s ease; }
      @media (hover:hover) {
        .schedule-list .game:hover { transform: translateY(-1px); background: rgba(255,255,255,0.03); box-shadow: 0 2px 10px rgba(0,0,0,.25); }
      }
    `;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }

  /* ---------- Init ---------- */
  function init() {
    injectStyle();
    attachImageGuards();
    initFilters();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();