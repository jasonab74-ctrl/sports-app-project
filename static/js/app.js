// static/js/app.js
// Top Headlines UX: filters, de-dupe display, thumbnails, paywall lock, save/copy, timeago.

(function () {
  const $ = (q, root = document) => root.querySelector(q);
  const $$ = (q, root = document) => Array.from(root.querySelectorAll(q));
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }
  };

  const FILTER_KEY = "newsFilter";      // all | official | insiders | national
  const SAVED_KEY  = "savedArticles";   // array of link hashes

  const timeAgo = (ts) => {
    const diff = Date.now() - ts;
    const m = Math.max(0, Math.floor(diff / 60000));
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m/60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h/24);
    return `${d}d ago`;
  };

  const hash = (s) => {
    let h = 0, i, chr;
    for (i = 0; i < s.length; i++) {
      chr = s.charCodeAt(i);
      h = ((h << 5) - h) + chr;
      h |= 0;
    }
    return "h" + Math.abs(h);
  };

  function getSeedItems() {
    const tag = $("#seed-items");
    if (!tag) return [];
    try { return JSON.parse(tag.textContent).items || []; } catch { return []; }
  }

  async function fetchNews() {
    try {
      const r = await fetch("./static/data/news.json?v=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error("news.json not found");
      return await r.json();
    } catch {
      // Fallback to seed only
      return { items: getSeedItems(), updated: Date.now() };
    }
  }

  function pillsInit() {
    const last = store.get(FILTER_KEY, "all");
    $$(".pills .pill").forEach(p => {
      const val = p.textContent.trim().toLowerCase();
      if (val === (last === "all" ? "all" : (last.endsWith("s") ? last : last + "s"))) {
        p.classList.add("active");
      }
      p.addEventListener("click", () => {
        $$(".pills .pill").forEach(x=>x.classList.remove("active"));
        p.classList.add("active");
        const key = p.textContent.trim().toLowerCase();
        const filter = key === "all" ? "all" :
          (key === "official" || key === "insiders" || key === "national") ? key.replace(/s$/,'') : "all";
        store.set(FILTER_KEY, filter);
        render(); // re-render with new filter
      });
    });
  }

  function cardHTML(it, savedSet) {
    const locked = it.paywall ? `<span class="lock" title="Likely paywalled">🔒</span>` : "";
    const img = it.image ? `<div class="card-thumb"><img loading="lazy" src="${it.image}" alt=""></div>` : "";
    const linkHash = hash(it.link);
    const isSaved = savedSet.has(linkHash);
    const saveTitle = isSaved ? "Remove from Saved" : "Save";
    const saveIcon  = isSaved ? "★" : "☆";

    return `
      <article class="card ${it.tier}">
        ${img}
        <div class="card-body">
          <div class="card-kickers">
            <span class="kicker">${it.tier}</span>
            <span class="kicker src">${it.source}${locked}</span>
          </div>
          <a class="card-title" href="${it.link}" target="_blank" rel="noopener">${it.title}</a>
          <div class="card-meta" data-ts="${it.ts}">
            <span class="ago">${timeAgo(it.ts)}</span> • ${it.source}
          </div>
          <div class="card-actions">
            <button class="btn-icon copy" data-url="${it.link}" title="Copy link">⎘</button>
            <button class="btn-icon save" data-id="${linkHash}" data-url="${it.link}" data-title="${it.title}" title="${saveTitle}">${saveIcon}</button>
          </div>
        </div>
      </article>`;
  }

  function attachCardEvents(root) {
    // copy link
    root.querySelectorAll(".btn-icon.copy").forEach(btn => {
      btn.addEventListener("click", async () => {
        const url = btn.getAttribute("data-url");
        try { await navigator.clipboard.writeText(url); btn.textContent = "✓"; setTimeout(()=>btn.textContent="⎘", 800); } catch {}
      });
    });
    // save/unsave
    root.querySelectorAll(".btn-icon.save").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const saved = new Set(store.get(SAVED_KEY, []));
        if (saved.has(id)) { saved.delete(id); btn.textContent = "☆"; btn.title = "Save"; }
        else { saved.add(id); btn.textContent = "★"; btn.title = "Remove from Saved"; }
        store.set(SAVED_KEY, Array.from(saved));
      });
    });
  }

  let newsCache = null;
  async function render() {
    const grid = $("#news-grid");
    const heroWrap = $("#news-hero");
    const heroMeta = $("#news-hero-meta");
    if (!grid || !heroWrap) return;

    if (!newsCache) {
      $("#news-status")?.removeAttribute("hidden");
      newsCache = await fetchNews();
      $("#news-status")?.setAttribute("hidden", "");
    }

    const filter = store.get(FILTER_KEY, "all"); // 'all' | 'official' | 'insider' | 'national'
    const savedSet = new Set(store.get(SAVED_KEY, []));

    // choose list with pinned official at top already (collector does this),
    // but we still filter on the client when user taps pills
    let list = newsCache.items || [];
    if (filter !== "all") {
      const map = { insider: "insiders", official: "official", national: "national" };
      const expect = filter === "insider" ? "insiders" : map[filter] || filter;
      list = list.filter(it => it.tier === expect || it.tier === filter);
    }

    // HERO = first item with image, else top item
    let hero = list.find(x => x.image) || list[0];
    if (hero) {
      heroWrap.innerHTML = `<a class="hero-img" href="${hero.link}" target="_blank" rel="noopener" aria-label="${hero.title}">
        <img src="${hero.image || ""}" alt="">
      </a>`;
      heroMeta.innerHTML = `
        <div class="meta-row">
          <span class="pill small">${hero.tier}</span>
          <span class="pill small">${hero.source}</span>
        </div>
        <a class="hero-title" href="${hero.link}" target="_blank" rel="noopener">${hero.title}</a>
        <div class="muted small">${timeAgo(hero.ts)}</div>`;
    }

    // CARDS (skip the hero if it appears in filtered list)
    const rest = list.filter(x => !hero || x.link !== hero.link);
    const html = rest.slice(0, 21).map(it => cardHTML(it, savedSet)).join("");
    grid.innerHTML = html;
    attachCardEvents(grid);
  }

  // timeago auto-tick
  setInterval(() => {
    $$(".card-meta").forEach(el => {
      const ts = Number(el.getAttribute("data-ts"));
      if (ts) { $(".ago", el).textContent = timeAgo(ts); }
    });
  }, 60 * 1000);

  // Keyboard navigation: j/k or arrows
  document.addEventListener("keydown", (e) => {
    if (!["ArrowLeft","ArrowRight","ArrowUp","ArrowDown","j","k"].includes(e.key)) return;
    const cards = $$(".card-title");
    if (!cards.length) return;
    const active = document.activeElement;
    let idx = cards.indexOf(active);
    if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === "j") idx++;
    if (e.key === "ArrowLeft"  || e.key === "ArrowUp"   || e.key === "k") idx--;
    idx = Math.max(0, Math.min(cards.length-1, idx));
    cards[idx].focus();
  });

  // bootstrap
  pillsInit();
  render();
})();
