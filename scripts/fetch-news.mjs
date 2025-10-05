// scripts/fetch-news.mjs
// Live RSS fetch -> static/teams/purdue-mbb/items.json
// Node 20+ only (uses global fetch). No external deps.

import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";

const root = process.cwd();
const cfgPath = resolve(root, "static/teams/purdue-mbb/feeds.json");
const outPath = resolve(root, "static/teams/purdue-mbb/items.json");

function loadJSON(p) { return JSON.parse(readFileSync(p, "utf8")); }
const cfg = loadJSON(cfgPath);

const MAX = cfg.max_items ?? 12;
const MIN = cfg.min_live_threshold ?? 6;

// --- tiny helpers ---
const textBetween = (s, a, b) => {
  const i = s.indexOf(a);
  if (i === -1) return null;
  const j = s.indexOf(b, i + a.length);
  if (j === -1) return null;
  return s.slice(i + a.length, j);
};
const isoOrNull = (d) => {
  const t = Date.parse(d);
  return Number.isFinite(t) ? new Date(t).toISOString() : null;
};
const domain = (url) => {
  try { return new URL(url).hostname.replace(/^www\./, ""); }
  catch { return ""; }
};
const kindFrom = (url, declared) =>
  /youtube\.com|youtu\.be/.test(url) ? "video" : (declared || "article");

// Simple RSS/Atom parser (best-effort, no external deps)
function parseFeed(xml, declaredType) {
  const items = [];
  const isAtom = xml.includes("<feed");
  if (!isAtom) {
    // RSS <item>
    const parts = xml.split("<item").slice(1);
    for (const chunk of parts) {
      const item = chunk.split("</item>")[0] || chunk;
      const title = (textBetween(item, "<title>", "</title>") || "").replace(/<!\[CDATA\[|\]\]>/g, "").trim();
      const link  = (textBetween(item, "<link>", "</link>") || textBetween(item, '<link>', '</link>') || "").trim();
      const pub   = textBetween(item, "<pubDate>", "</pubDate>") || textBetween(item, "<dc:date>", "</dc:date>") || "";
      items.push({ title, link, published: isoOrNull(pub), type: kindFrom(link, declaredType) });
    }
  } else {
    // Atom <entry>
    const parts = xml.split("<entry").slice(1);
    for (const chunk of parts) {
      const entry = chunk.split("</entry>")[0] || chunk;
      const title = (textBetween(entry, "<title>", "</title>") || "").replace(/<!\[CDATA\[|\]\]>/g, "").trim();
      let link = "";
      const linkTag = entry.match(/<link[^>]+href="([^"]+)"/);
      if (linkTag) link = linkTag[1];
      const pub = textBetween(entry, "<updated>", "</updated>") || textBetween(entry, "<published>", "</published>") || "";
      items.push({ title, link, published: isoOrNull(pub), type: kindFrom(link, declaredType) });
    }
  }
  // Filter garbage
  return items.filter(i => i.title && i.link);
}

const SOURCE_BY_DOMAIN = {
  "purduesports.com": "PurdueSports.com",
  "si.com": "Sports Illustrated CBB",
  "cbssports.com": "CBS Sports CBB",
  "sports.yahoo.com": "Yahoo CBB",
  "jconline.com": "Journal & Courier",
  "247sports.com": "247Sports Purdue",
  "purdue.rivals.com": "Gold and Black (Rivals)",
  "youtube.com": "YouTube"
};

function normalizeItem(raw, declaredName, declaredTier) {
  const d = domain(raw.link);
  const source = SOURCE_BY_DOMAIN[d] || declaredName || d || "Unknown";
  const ts = raw.published ? Date.parse(raw.published) : Date.now();
  return {
    title: raw.title,
    link: raw.link,
    source,
    tier: declaredTier || "national",
    type: raw.type || "article",
    ts
  };
}

function dedupe(items) {
  const seen = new Set();
  const out = [];
  for (const it of items) {
    const key = `${it.title}__${it.link}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(it);
  }
  return out;
}

async function fetchAll() {
  const all = [];
  for (const src of (cfg.sources || [])) {
    try {
      const res = await fetch(src.url, { headers: { "user-agent": "gh-actions (+team-hub)" } });
      if (!res.ok) throw new Error(`${src.name} HTTP ${res.status}`);
      const xml = await res.text();
      const parsed = parseFeed(xml, src.type).map(item => normalizeItem(item, src.name, src.tier));
      // keep most recent 5 per source to avoid floods
      parsed.sort((a,b)=>b.ts-a.ts);
      all.push(...parsed.slice(0, 5));
    } catch (e) {
      console.warn(`WARN feed ${src.name}: ${e.message}`);
    }
  }
  let items = dedupe(all).sort((a,b)=>b.ts-a.ts).slice(0, MAX);

  // fallback to seed if live is too thin
  if (items.length < MIN && cfg.fallback_seed) {
    try {
      const seed = loadJSON(resolve(root, cfg.fallback_seed));
      const now = Date.now();
      const seeded = (seed.items || []).map((s, i) => ({ ...s, ts: now - i * 3600_000 }));
      items = dedupe([...seeded, ...items]).sort((a,b)=>b.ts-a.ts).slice(0, MAX);
      console.log(`Fallback used: live ${all.length} → final ${items.length}`);
    } catch (e) {
      console.warn(`WARN fallback failed: ${e.message}`);
    }
  }

  // write
  const payload = { items };
  const prev = (() => {
    try { return readFileSync(outPath, "utf8"); } catch { return ""; }
  })();
  const next = JSON.stringify(payload, null, 2);

  if (prev.trim() !== next.trim()) {
    writeFileSync(outPath, next, "utf8");
    console.log(`WROTE ${items.length} items → ${outPath}`);
  } else {
    console.log(`No change in items.json`);
  }
}

// Ensure path exists in commits (optional tidy)
try {
  execSync('git status', { stdio: 'ignore' });
} catch {}

fetchAll().catch(e => {
  console.error(e);
  process.exitCode = 1;
});