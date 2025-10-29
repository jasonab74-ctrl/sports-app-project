(function () {
  const ITEMS_URL = "static/teams/purdue-mbb/items.json";
  const SOURCES_URL = "static/sources.json";
  const updatedEl = document.getElementById("updated");
  const cardsEl = document.getElementById("cards");
  const sourcesEl = document.getElementById("sources");

  const fmtDate = (iso) => {
    try {
      const d = new Date(iso);
      // valid date?
      if (isNaN(d.getTime())) return "—";
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch { return "—"; }
  };

  const fmtUpdated = (iso) => {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return "Updated";
      const opts = { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" };
      return `Updated ${d.toLocaleDateString(undefined, opts)}`;
    } catch { return "Updated"; }
  };

  const escapeHTML = (s) =>
    s.replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

  async function loadJSON(url) {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`Failed to fetch ${url}`);
    return res.json();
  }

  function renderSources(list) {
    sourcesEl.innerHTML = list.join(" · ");
  }

  function renderCards(items) {
    if (!items || !items.length) {
      cardsEl.innerHTML = `
        <div class="card" style="grid-column:span 12">
          <div class="kicker">Collector Debug <span>Just now</span></div>
          <h3>No Purdue MBB stories matched filters</h3>
          <p>Collector ran successfully but strict filters removed everything. This is a fallback card.</p>
        </div>`;
      return;
    }
    const html = items.map(it => {
      const title = escapeHTML(it.title || "");
      const summary = escapeHTML(it.summary || "");
      const src = escapeHTML(it.source || "");
      const date = fmtDate(it.published);
      const url = it.url || "#";
      return `
      <article class="card">
        <div class="kicker"><span>${src}</span><span>${date}</span></div>
        <a href="${url}" target="_blank" rel="noopener">
          <h3>${title}</h3>
          <p>${summary}</p>
        </a>
      </article>`;
    }).join("");
    cardsEl.innerHTML = html;
  }

  async function init() {
    try {
      const [data, sources] = await Promise.all([loadJSON(ITEMS_URL), loadJSON(SOURCES_URL)]);
      renderSources(sources.display || sources.sources || []);
      updatedEl.textContent = fmtUpdated(data.updated || data.generated_at || new Date().toISOString());
      renderCards(data.items || []);
    } catch (err) {
      updatedEl.textContent = "Updated (load error)";
      cardsEl.innerHTML = `
        <div class="card" style="grid-column:span 12">
          <div class="kicker"><span>Error</span><span>Now</span></div>
          <h3>Couldn’t load feed</h3>
          <p>${escapeHTML(err.message || String(err))}</p>
        </div>`;
    }
  }

  init();
})();