// pro.js — render clean headline list without images

async function loadHeadlines() {
  try {
    const response = await fetch("static/teams/purdue-mbb/items.json");
    if (!response.ok) throw new Error("Failed to load items.json");
    const data = await response.json();

    const container = document.getElementById("headlines");
    container.innerHTML = ""; // clear old

    const items = data.items || [];
    items.forEach(item => {
      const card = renderItemCard(item);
      container.appendChild(card);
    });

    const updated = new Date(data.updated);
    document.getElementById("last-updated").textContent =
      "Updated " + updated.toLocaleString();
  } catch (err) {
    console.error(err);
  }
}

function renderItemCard(item) {
  const card = document.createElement("a");
  card.className = "news-card";
  card.href = item.link;
  card.target = "_blank";
  card.rel = "noopener";

  // No image section at all
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