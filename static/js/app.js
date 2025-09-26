const DAILY_LIMIT = 8;          // top items for Daily Brief
const FEED_LIMIT  = 50;         // top items for Top Feed
const FALLBACK_IMG = "https://via.placeholder.com/240x180.png?text=Team+Hub";

const els = {
  team: document.getElementById("team"),
  refresh: document.getElementById("refresh"),
  daily: document.getElementById("daily"),
  dailyEmpty: document.getElementById("dailyEmpty"),
  dailyCount: document.getElementById("dailyCount"),
  feed: document.getElementById("feed"),
  feedEmpty: document.getElementById("feedEmpty"),
  feedCount: document.getElementById("feedCount"),
  tmpl: document.getElementById("card-template"),
};

function trustClass(level) {
  return `trust-${(level || "blog").replace(/[^a-z_]/gi,"")}`;
}

function fmtWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month:"short", day:"numeric", hour:"numeric", minute:"2-digit" });
}

function renderCard(item) {
  const frag = els.tmpl.content.cloneNode(true);
  const aThumb = frag.querySelector(".thumb");
  const img = frag.querySelector("img");
  const aTitle = frag.querySelector(".title");
  const source = frag.querySelector(".source");
  const when = frag.querySelector(".when");
  const trust = frag.querySelector(".trust");
  const summary = frag.querySelector(".summary");

  const url = item.url || "#";
  aThumb.href = url;
  aTitle.href = url;

  img.src = item.image_url || FALLBACK_IMG;
  img.alt = item.title || "";

  aTitle.textContent = item.title || "Untitled";
  source.textContent = item.source || "Source";
  when.textContent = fmtWhen(item.published_at);

  const level = (item.trust_level || "blog");
  trust.textContent = level.replace("_"," ");
  trust.classList.add(trustClass(level));

  summary.textContent = item.summary || "";

  return frag;
}

async function loadTeam(team) {
  // Items JSON is expected at /static/teams/<team>/items.json (same repo)
  const url = `./static/teams/${encodeURIComponent(team)}/items.json?ts=${Date.now()}`;

  // Show loading skeletons (simple)
  els.daily.innerHTML = "";
  els.feed.innerHTML = "";
  els.dailyEmpty.classList.add("hidden");
  els.feedEmpty.classList.add("hidden");
  els.dailyCount.textContent = "";
  els.feedCount.textContent = "";

  let data = [];
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    data = await r.json();
  } catch (err) {
    console.error(err);
    els.feedEmpty.classList.remove("hidden");
    els.feedEmpty.textContent = "Couldn’t load the feed. Check that static/teams/" + team + "/items.json exists.";
    return;
  }

  // Sort newest first by published_at (if present)
  data.sort((a,b) => new Date(b.published_at||0) - new Date(a.published_at||0));

  const dailyItems = data.slice(0, DAILY_LIMIT);
  const feedItems  = data.slice(0, FEED_LIMIT);

  if (dailyItems.length) {
    const df = document.createDocumentFragment();
    dailyItems.forEach(it => df.appendChild(renderCard(it)));
    els.daily.appendChild(df);
    els.dailyCount.textContent = `${dailyItems.length}`;
  } else {
    els.dailyEmpty.classList.remove("hidden");
  }

  if (feedItems.length) {
    const df2 = document.createDocumentFragment();
    feedItems.forEach(it => df2.appendChild(renderCard(it)));
    els.feed.appendChild(df2);
    els.feedCount.textContent = `${feedItems.length}`;
  } else {
    els.feedEmpty.classList.remove("hidden");
  }
}

// Wire up
els.refresh.addEventListener("click", () => loadTeam(els.team.value));
els.team.addEventListener("change", () => loadTeam(els.team.value));
loadTeam(els.team.value);
