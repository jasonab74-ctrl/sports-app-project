// static/js/pro.js
// Purdue MBB News Frontend — text-only cards (no images)

async function loadHeadlines() {
  try {
    const response = await fetch("static/teams/purdue-mbb/items.json", {
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Failed to load items.json");
    const data = await response.json();

    const container = document.getElementById("headlines");
    container.innerHTML = "";

    const items = data.items || [];
    if (items.length === 0) {
      container.innerHTML = `<p class="empty-msg">No recent headlines available.</p>`;
      return;
    }

    items.forEach(item => {
      const card = renderItemCard(item);
      container.appendChild(card);
    });

    const updated = new Date(data.updated);
    const stamp = document.getElementById("last-updated");
    if (stamp) stamp.textContent = "Updated " + updated.toLocaleString();
  } catch (err) {
    console.error("Headline load error:", err);
    const container = document.getElementById("headlines");
    if (container)
      container.innerHTML = `<p class="empty-msg">Failed to load headlines.</p>`;
  }
}

function renderItemCard(item) {
  const card = document.createElement("a");
  card.className = "news-card";
  card.href = item.link;
  card.target = "_blank";
  card.rel = "noopener noreferrer";

  // clean text-only layout
  card.innerHTML = `
    <div class="news-card-body">
      <div class="news-card-source">${item.source}</div>
      <div class="news-card-title">${item.title}</div>
      <div class="news-card-date">${item.date}</div>
    </div>
  `;

  return card;
}

document.addEventListener("DOMContentLoaded", loadHeadlines);