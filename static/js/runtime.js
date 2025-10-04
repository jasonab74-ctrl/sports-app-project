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
      // swap to local brand poster
      img.onerror = null; // break loops
      img.removeAttribute('srcset');
      img.src = poster;
      return;
    }

    // replace <img> with initials tile
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

  /* ---------- Chips: auto-hide if not wired ---------- */
  function hideDeadChips() {
    // If filter chips exist but we haven't implemented filtering yet,
    // hide them to avoid “broken control” vibes.
    const chipBars = document.querySelectorAll('.panel-hd .chips, .chips');
    chipBars.forEach((bar) => {
      // If there’s no data attribute indicating behavior, hide them.
      if (!bar.hasAttribute('data-filter-ready')) {
        bar.hidden = true;
        bar.style.display = 'none';
      }
    });
  }

  /* ---------- Micro CSS polish (safe to inject) ---------- */
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
    hideDeadChips();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();