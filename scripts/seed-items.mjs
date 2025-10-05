// Simple, safe hourly writer: copies seed -> items and freshens timestamps.
// No external fetches. Zero deps. Works on GH Actions and locally.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const seedPath = resolve(root, "static/teams/purdue-mbb/items.seed.json");
const outPath  = resolve(root, "static/teams/purdue-mbb/items.json");

const now = Date.now();

// Read seed
const seedRaw = readFileSync(seedPath, "utf8");
const seed = JSON.parse(seedRaw);

// Freshen timestamps so newest items float up without changing links/titles.
// We keep order as-is but assign descending timestamps from "now".
const items = (seed.items ?? []).map((item, idx) => {
  const ts = now - idx * 60 * 60 * 1000; // 1 hour spacing
  return { ...item, ts };
});

// Write items
writeFileSync(outPath, JSON.stringify({ items }, null, 2), "utf8");

console.log(`Wrote ${items.length} items → ${outPath}`);