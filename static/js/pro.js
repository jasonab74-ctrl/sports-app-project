(function () {
  const NEWS_URL = "static/teams/purdue-mbb/items.json";
  const BOARD_URL = "static/teams/purdue-mbb/board.json";

  const updatedEl = document.getElementById("updated");
  const cardsEl = document.getElementById("cards");
  const tabButtons = Array.from(document.querySelectorAll(".tab"));

  const escapeHTML = (s) =>
    String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const fmtShortDate = (iso) => {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return "";
      const now = new Date();
      const opts = { month: "short", day: "numeric" };
      const base = d.toLocaleDateString(undefined, opts);
      return d.getFullYear() === now.getFullYear() ? base : `${base}, ${d.getFullYear()}`;
    } catch { return ""; }
  };

  const fmtUpdated = (iso) => {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return "Updated";
      const optsDate = { month: "short", day: "numeric" };
      const optsTime = { hour: "numeric", minute: "2-digit" };
      const datePart = d.toLocaleDateString(undefined, optsDate);
      const timePart = d.toLocaleTimeString(undefined, optsTime);
      const y = d.getFullYear();
      const showYear = y !== (new Date()).getFullYear();
      return `Updated ${datePart}${showYear ? ", " + y : ""}, ${timePart}`;
    } catch { return "Updated"; }
  };

  async function getJSON(url) {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`Fetch failed: ${url} (${res.status})`);
    return res.json();
  }

  function renderCards(items, isBoard) {
    if (!items || !items.length) {
      cardsEl.innerHTML = `
        <div class="card" style="grid-column:span 12">
          <div class="kicker"><span>${isBoard ? "Fan Board" : "News"}</span><span>—</span></div>
          <h3>No recent ${isBoard ? "threads" : "stories"} found</h3>
          <p>Check back soon.</p>
        </div>`;
      return;
    }

    cardsEl.innerHTML = items.map(it => {
      const title = escapeHTML(it.title);
      const summary = escapeHTML(it.summary || (isBoard ? "Fan discussion thread" : ""));
      const src = escapeHTML(it.source || (isBoard ? "On3 — Purdue MBB Board" : "Source"));
      const date = fmtShortDate(it.published || it.published_iso || it.published_at);
      const url = it.url || it.link || "#";
      return `
        <article class="card">
          <div class="kicker"><span>${src}</span><span>${date}</span></div>
          <a href="${url}" target="_blank" rel="noopener noreferrer">
            <h3>${title}</h3>
            <p>${summary}</p>
          </a>
        </article>
      `;
    }).join("");
  }

  function setUpdated(iso) {
    updatedEl.textContent = fmtUpdated(iso || new Date().toISOString());
  }

  async function showTab(kind) {
    tabButtons.forEach(b => b.classList.toggle("active", b.dataset.tab === kind));
    try {
      if (kind === "board") {
        const data = await getJSON(BOARD_URL);
        renderCards(data.items || [], true);
        setUpdated(data.generated_at);
      } else {
        const data = await getJSON(NEWS_URL);
        renderCards(data.items || [], false);
        setUpdated(data.generated_at);
      }
    } catch (err) {
      cardsEl.innerHTML = `
        <div class="card" style="grid-column:span 12">
          <div class="kicker"><span>Error</span><span>Now</span></div>
          <h3>Couldn’t load ${kind === "board" ? "board" : "news"} feed</h3>
          <p>${escapeHTML(err.message || String(err))}</p>
        </div>`;
      setUpdated();
    }
  }

  // events
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => showTab(btn.dataset.tab));
  });

  // initial load = News
  showTab("news");
})();