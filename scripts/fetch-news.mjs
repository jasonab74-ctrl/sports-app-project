/**
 * Build items.json from configured feeds (static/teams/purdue-mbb/sources.json)
 * Output: static/teams/purdue-mbb/items.json
 * – Keeps site fully static; runs in GitHub Actions pre-build.
 * – Dedupes, sorts by published date desc, caps to 10.
 */

import fs from 'fs';
import fetch from 'node-fetch';
import { XMLParser } from 'fast-xml-parser';

const SOURCES_FILE = 'static/teams/purdue-mbb/sources.json';
const OUT_FILE     = 'static/teams/purdue-mbb/items.json';

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  removeNSPrefix: true,
  textNodeName: '#text'
});

function readJSON(p, def) { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return def; } }
function writeJSON(p, data) {
  fs.mkdirSync(p.split('/').slice(0, -1).join('/'), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(data, null, 2));
}
function toDateSafe(v) {
  const d = new Date(v); return isNaN(+d) ? null : d;
}
function sanitize(str) {
  return String(str || '').replace(/\s+/g, ' ').trim();
}
function takeFirst(arr) { return Array.isArray(arr) ? arr[0] : arr; }

function fromRSS(xml, source) {
  const out = [];
  const ch = xml?.rss?.channel || xml?.channel;
  const items = ch?.item || [];
  const list = Array.isArray(items) ? items : [items];
  for (const it of list) {
    const title = sanitize(it?.title);
    const link = sanitize(it?.link);
    const pub = toDateSafe(it?.pubDate || it?.published || it?.updated);
    if (!title || !link) continue;
    out.push({
      title,
      link,
      source: source.name,
      tier: source.tier,
      ts: pub ? +pub : Date.now(),
      type: 'article'
    });
  }
  return out;
}

function fromAtom(xml, source) {
  const out = [];
  const entries = xml?.feed?.entry || [];
  const list = Array.isArray(entries) ? entries : [entries];
  for (const e of list) {
    const title = sanitize(e?.title?.['#text'] || e?.title);
    let link = '';
    if (Array.isArray(e?.link)) {
      const alt = e.link.find(l => (l['@_rel'] || '') === 'alternate');
      link = alt?.['@_href'] || e.link[0]?.['@_href'] || '';
    } else {
      link = e?.link?.['@_href'] || e?.link || '';
    }
    const pub = toDateSafe(e?.updated || e?.published);
    if (!title || !link) continue;
    out.push({
      title,
      link: sanitize(link),
      source: source.name,
      tier: source.tier,
      ts: pub ? +pub : Date.now(),
      type: 'article'
    });
  }
  return out;
}

function fromJSONFeed(json, source) {
  const out = [];
  const items = json?.items || [];
  for (const it of items) {
    const title = sanitize(it?.title);
    const link  = sanitize(it?.url || it?.external_url);
    const pub   = toDateSafe(it?.date_published || it?.date_modified);
    if (!title || !link) continue;
    out.push({
      title,
      link,
      source: source.name,
      tier: source.tier,
      ts: pub ? +pub : Date.now(),
      type: 'article'
    });
  }
  return out;
}

async function fetchFeed(source) {
  try {
    const r = await fetch(source.feed, { headers: { 'user-agent': 'Mozilla/5.0 (News Sync)' }, redirect: 'follow' });
    const text = await r.text();
    // Try JSON Feed first
    try {
      const data = JSON.parse(text);
      if (data && (Array.isArray(data.items) || data.version?.includes('jsonfeed'))) {
        return fromJSONFeed(data, source);
      }
    } catch {}
    // Then XML (RSS/Atom)
    const xml = parser.parse(text);
    if (xml?.rss || xml?.channel) return fromRSS(xml, source);
    if (xml?.feed) return fromAtom(xml, source);
  } catch (e) {
    console.log(`feed: ${source.name} failed (${e?.message || e})`);
  }
  return [];
}

function dedupeSortCap(all) {
  const seen = new Set();
  const out = [];
  for (const i of all) {
    const key = (i.link || '').toLowerCase() + '|' + (i.title || '').toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(i);
  }
  out.sort((a,b) => b.ts - a.ts);
  return out.slice(0, 10);
}

(async function run() {
  const sources = readJSON(SOURCES_FILE, []);
  if (!Array.isArray(sources) || sources.length === 0) {
    console.log('news: no sources configured.');
    return;
  }

  const batches = await Promise.all(sources.map(fetchFeed));
  const combined = dedupeSortCap(batches.flat());

  // Preserve structure you already use: { items: [...] }
  const payload = { items: combined.map(i => ({
    title: i.title,
    link: i.link,
    source: i.source,
    tier: i.tier,
    type: i.type,
    ts: i.ts
  }))};

  writeJSON(OUT_FILE, payload);
  console.log(`news: wrote ${payload.items.length} items`);
})().catch(err => {
  console.error('news: fatal', err?.message || err);
  process.exitCode = 0; // do not fail the build if feeds glitch
});