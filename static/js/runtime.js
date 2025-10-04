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
    } catch {
      return {};
    }
  }

  function hostFromLink(img) {
    try {
      const a = img.closest('a');
      if (!a) return '';
      return new URL(a.href).hostname.toLowerCase();
    } catch {
      return '';
    }
  }

  /* ---------- Image fail-safe (no more blue “?”) ---------- */
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
    const imgs = document.querySelectorAll('img.hero-img, img.card-img');
    imgs.forEach((img) => {
      img.addEventListener('error', () => swapToPosterOrFallback(img), { once: true });
    });
  }

  /* ---------- Filters (chips) ---------- */
  function initFilters() {
    const bar = document.querySelector('.panel-hd .chips[data-filter-ready]');
    const grid = document.getElementById('news-grid');
    if (!bar || !grid) return;

    const chips = Array.from(bar.querySelectorAll('.chip'));
    const cards = Array.from(grid.querySelectorAll('.card'));

    function apply(filter) {
      cards.forEach((card) => {
        const tier = card.getAttribute('data-tier') || 'all';
        const show = filter === 'all' ? true : (tier === filter);
        card.style.display = show ? '' : 'none';
      });
      chips.forEach((c) => {
        const active = c.getAttribute('data-filter') === filter;
        c.classList.toggle('is-active', active);
        c.setAttribute('aria-pressed', String(active));
      });
    }

    bar.addEventListener('click', (e) => {
      const btn = e.target.closest('.chip');
      if (!btn) return;
      const filter = btn.getAttribute('data-filter') || 'all';
      apply(filter);
    });

    // default state
    apply('all');
  }

  /* ---------- Micro CSS polish ---------- */
  function injectStyle() {
    const css = `
      /* Hero spacing nudge on small screens */
      .hero .hero-img-wrap { margin-bottom: 8px; }

      /* Schedule row affordance */
      .schedule-list .game {
        transition: transform .12s ease, background-color .12s ease, box-shadow .12s ease;
        border-radius: 10px;
      }
      @media (hover:hover) {
        .schedule-list .game:hover {
          transform: translateY(-1px);
          background: rgba(255,255,255,0.03);
          box-shadow: 0 2px 10px rgba(0,0,0,.25);
        }
      }
      .schedule-list .game:focus-visible {
        outline: 2px solid #f2c94c;
        outline-offset: 2px;
      }

      /* Chips active state */
      .chips { display:flex; gap:.5rem; flex-wrap:wrap; }
      .chip {
        background: rgba(255,255,255,.06);
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 999px;
        padding: .4rem .8rem;
        font: inherit;
        color: inherit;
        cursor: pointer;
      }
      .chip.is-active {
        background: rgba(242,201,76,.16);
        border-color: rgba(242,201,76,.7);
      }
      .chip:focus-visible { outline:2px solid #f2c94c; outline-offset:2px; }
    `;
    const style = document.createElement('style');
    style.setAttribute('data-injected', 'runtime-polish');
    style.textContent = css;
    document.head.appendChild(style);
  }

  /* ---------- Init ---------- */
  function init() {
    injectStyle();
    attachImageGuards();
    initFilters();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();