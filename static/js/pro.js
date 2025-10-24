(async function () {
  const GRID = document.getElementById("news-grid");
  const EMPTY = document.getElementById("news-empty");
  const BUILD_LINE = document.getElementById("build-line");
  const YEAR_EL = document.getElementById("year");

  // stamp the current year down in the footer
  if (YEAR_EL) {
    YEAR_EL.textContent = new Date().getFullYear();
  }

  async function fetchItems() {
    try {
      const res = await fetch("static/teams/purdue-mbb/items.json", {
        cache: "no-store"
      });
      if (!res.ok) throw new Error("items.json not ok");
      return await res.json();
    } catch (err) {
      console.error("Failed to load items.json", err);
      return { items: [] };
    }
  }

  async function fetchBuild() {
    try {
      const res = await fetch("static/build.json", {
        cache: "no-store"
      });
      if (!res.ok) throw new Error("build.json not ok");
      return await res.json();
    } catch (err) {
      console.error("Failed to load build.json", err);
      return null;
    }
  }

  function fmtDate(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
      });
    } catch (_) {
      return "";
    }
  }

  // Render 1 headline card
  function renderCard(item) {
    const title = item.title || "";
    const link = item.link || "#";
    const source = item.source || "";
    const dateStr = fmtDate(item.date);
    const imgUrl = item.image || null;

    // We'll render thumbnail if we have a URL.
    // If it 404s, onerror mark wrapper as .no-thumb (which shows fallback)
    const thumbHTML = imgUrl
      ? `
        <img
          class="thumb"
          src="${imgUrl}"
          alt=""
          onerror="this.closest('.thumb-wrap').classList.add('no-thumb'); this.remove();"
        />`
      : `
        <div class="thumb thumb-fallback">
          <div class="thumb-fallback-inner">No Image</div>
        </div>`;

    return `
      <a class="card" href="${link}" target="_blank" rel="noopener noreferrer">
        <div class="thumb-wrap">
          ${thumbHTML}
        </div>
        <div class="meta">
          <div class="source">${source}</div>
          <div class="title">${title}</div>
          <div class="date">${dateStr}</div>
        </div>
      </a>
    `;
  }

  function renderItems(items) {
    if (!GRID || !EMPTY) return;

    if (!items || !items.length) {
      GRID.innerHTML = "";
      EMPTY.classList.remove("hidden");
      return;
    }

    EMPTY.classList.add("hidden");
    GRID.innerHTML = items.map(renderCard).join("");
  }

  function renderBuildInfo(buildData) {
    if (!BUILD_LINE || !buildData) return;

    const ts = buildData.timestamp || "";
    const sha = buildData.commit || buildData.sha || "";
    const cnt = buildData.items_count != null ? buildData.items_count : "";

    // "updated X min ago"
    let ageText = "";
    if (ts) {
      const builtAt = new Date(ts);
      const now = new Date();
      const mins = Math.floor((now - builtAt) / 60000);
      if (mins <= 1) {
        ageText = "updated just now";
      } else if (mins < 60) {
        ageText = `updated ${mins} min ago`;
      } else {
        const hrs = Math.floor(mins / 60);
        ageText = `updated ${hrs} hr${hrs === 1 ? "" : "s"} ago`;
      }
    }

    BUILD_LINE.textContent =
      `Build: ${ts} • commit ${sha} • ${cnt} items • ${ageText}`;
  }

  // Load data in parallel
  const [data, buildData] = await Promise.all([fetchItems(), fetchBuild()]);

  renderItems(data.items || []);
  renderBuildInfo(buildData);

  // Add runtime CSS for thumbnail fallback / broken images
  injectThumbCSS();
})();

// Injects a tiny CSS block for thumb layout / fallback styling
function injectThumbCSS() {
  const css = `
  .thumb-wrap {
    position: relative;
    background: #1a1b1e;
    min-height: 160px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .thumb-wrap.no-thumb {
    background: #1a1b1e;
  }

  .thumb {
    width: 100%;
    height: 160px;
    object-fit: cover;
    background: #1a1b1e;
    display: block;
  }

  .thumb-fallback {
    width: 100%;
    height: 160px;
    background: #1a1b1e;
    color: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .thumb-fallback-inner {
    color: rgba(255,255,255,0.4);
    font-size: 1rem;
    font-weight: 500;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  `;
  const styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);
}