// static/js/pro.js
// Hydrates panels for Schedule / Rankings / Insiders / Roster
// Fully safe for GitHub Pages (relative paths only)

(function () {
  const BASE = "./";
  const url = (p) => BASE + p.replace(/^\//, "");
  const $ = (id) => document.getElementById(id);

  /* ---------- UTILITIES ---------- */
  function escapeHtml(s = "") {
    return (s + "").replace(/[&<>"']/g, (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[c])
    );
  }

  function fmtLocal(iso) {
    try {
      const dt = new Date(iso);
      const d = dt.toLocaleDateString([], {
        month: "2-digit",
        day: "2-digit",
      });
      const t = dt.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      return `${d}, ${t} local`;
    } catch {
      return iso;
    }
  }

  async function loadJSON(path) {
    try {
      const res = await fetch(url(path), { cache: "no-store" });
      if (!res.ok) throw new Error(res.statusText);
      return await res.json();
    } catch (e) {
      console.warn("Failed to load", path, e);
      return null;
    }
  }

  /* ---------- SCHEDULE PANEL ---------- */
  function renderSchedule(data) {
    const mount = $("scheduleList");
    if (!mount) return;

    if (!data || !Array.isArray(data.games) || !data.games.length) {
      mount.innerHTML = `<div class="muted small">No upcoming games.</div>`;
      return;
    }

    // Filter for upcoming games (now - 3h safety)
    const now = Date.now() - 3 * 60 * 60 * 1000;
    const upcoming = data.games
      .filter((g) => new Date(g.utc).getTime() >= now)
      .slice(0, 8);

    if (!upcoming.length) {
      mount.innerHTML = `<div class="muted small">No upcoming games.</div>`;
      return;
    }

    mount.innerHTML = upcoming
      .map((g) => {
        const odds = Array.isArray(g?.odds?.consensus)
          ? g.odds.consensus
          : [];
        let head =
          odds.find(
            (o) => o.spread !== null && o.spread !== undefined
          ) || odds[0];
        const oddsLine = head
          ? `<div class="link-meta">Odds: <strong>${escapeHtml(
              head.book
            )}</strong> • ${
              head.spread !== null && head.spread !== undefined
                ? `Spread: ${head.spread}`
                : ""
            }${head.total ? ` • Total: ${head.total}` : ""}${
              head.moneyline ? ` • ML: ${head.moneyline}` : ""
            }</div>`
          : "";

        return `
          <a class="link-card" href="#" tabindex="0">
            <div class="link-logo">•</div>
            <div class="link-body">
              <div class="link-title">${escapeHtml(
                g.opponent || "TBD"
              )}</div>
              <div class="link-meta">• ${escapeHtml(g.venue || "Neutral")}</div>
              <div class="link-meta">• ${fmtLocal(g.utc)}</div>
              ${oddsLine}
            </div>
          </a>`;
      })
      .join("");

    // Optional footer “last updated”
    const updated = data.updated
      ? new Date(data.updated).toLocaleString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";
    if (updated) {
      const footer = document.createElement("div");
      footer.className = "footer-note small";
      footer.textContent = `Updated ${updated}`;
      mount.parentNode.appendChild(footer);
    }
  }

  /* ---------- PLACEHOLDER RANKINGS / INSIDERS / ROSTER (expand later) ---------- */
  function renderRankings() {}
  function renderInsiders() {}
  function renderRoster() {}

  /* ---------- MASTER HYDRATOR ---------- */
  async function hydratePanels() {
    // Schedule
    const sched = await loadJSON("static/teams/purdue-mbb/schedule.json");
    renderSchedule(sched);

    // Stubs for other panels (future use)
    // const ranks = await loadJSON("static/teams/purdue-mbb/rankings.json"); renderRankings(ranks);
    // const insiders = await loadJSON("static/teams/purdue-mbb/insiders.json"); renderInsiders(insiders);
    // const roster = await loadJSON("static/teams/purdue-mbb/roster.json"); renderRoster(roster);
  }

  /* ---------- EXPORT ---------- */
  window.PRO = window.PRO || {};
  window.PRO.hydratePanels = hydratePanels;
})();
