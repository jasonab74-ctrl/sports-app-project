// Build-time artwork cacher for GitHub Pages.
// - Fetches article pages for whitelisted hosts
// - Extracts og:image / twitter:image
// - Downscales & saves to /static/cache/*.jpg
// - Rewrites items.json image fields to local cache paths

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import fetch from 'node-fetch';
import { JSDOM } from 'jsdom';
import sharp from 'sharp';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');

const TEAM = 'purdue-mbb'; // this project’s team slug
const ITEMS_PATH = path.join(ROOT, 'static', 'teams', TEAM, 'items.json');
const CACHE_DIR   = path.join(ROOT, 'static', 'cache');

const OFFICIAL_HOSTS = new Set([
  'purduesports.com',
  'youtube.com', 'youtu.be',
  'jconline.com',
  'hammerandrails.com',
  'sbnation.com',
  'si.com', 'img.si.com',
  'espn.com', 'espncdn.com'
]);

function ensureDirs() { fs.mkdirSync(CACHE_DIR, { recursive: true }); }

const readJSON = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const writeJSON = (p, obj) => fs.writeFileSync(p, JSON.stringify(obj, null, 2));

function etld1(host) {
  if (!host) return '';
  const parts = host.toLowerCase().split('.').filter(Boolean);
  return parts.length <= 2 ? host.toLowerCase() : parts.slice(-2).join('.');
}

function shouldCache(urlStr) {
  try {
    const u = new URL(urlStr);
    const host = etld1(u.host);
    if (process.env.OFFICIAL_ONLY === '1') {
      return OFFICIAL_HOSTS.has(host);
    }
    return true;
  } catch { return false; }
}

async function getOgImage(link) {
  try {
    const res = await fetch(link, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (ArtCacheBot/1.0)',
        'Accept': 'text/html,application/xhtml+xml'
      },
      redirect: 'follow',
      // node-fetch v3 doesn't support timeout option; use AbortController if needed.
    });
    if (!res.ok) return null;
    const html = await res.text();
    const dom = new JSDOM(html);
    const doc = dom.window.document;

    const pick = (sel) => {
      const el = doc.querySelector(sel);
      return el?.getAttribute('content')?.trim() || null;
    };

    const cands = [
      pick('meta[property="og:image:secure_url"]'),
      pick('meta[property="og:image:url"]'),
      pick('meta[property="og:image"]'),
      pick('meta[name="og:image"]'),
      pick('meta[name="twitter:image"]'),
      pick('meta[property="twitter:image"]')
    ].filter(Boolean);

    if (!cands.length) return null;

    // Resolve relative URLs against page URL
    return new URL(cands[0], link).toString();
  } catch {
    return null;
  }
}

async function downloadThumb(src, destPath) {
  const res = await fetch(src, {
    headers: { 'User-Agent': 'Mozilla/5.0 (ArtCacheBot/1.0)' },
    redirect: 'follow'
  });
  if (!res.ok) throw new Error('bad fetch ' + res.status);
  const buf = Buffer.from(await res.arrayBuffer());

  // Convert to JPEG thumbnail (800px max width)
  const out = await sharp(buf)
    .resize({ width: 800, withoutEnlargement: true })
    .jpeg({ quality: 78 })
    .toBuffer();

  fs.writeFileSync(destPath, out);
}

function hashName(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) { h = (h * 33) ^ str.charCodeAt(i); }
  return (h >>> 0).toString(16);
}

(async function main() {
  ensureDirs();
  if (!fs.existsSync(ITEMS_PATH)) {
    console.error('Missing items file:', ITEMS_PATH);
    process.exit(1);
  }

  const data = readJSON(ITEMS_PATH);
  const items = Array.isArray(data) ? data : (data.items || []);

  let changed = false;

  for (const item of items) {
    const link = item.link;
    if (!link || !shouldCache(link)) continue;

    // Already cached?
    if (item.image && /^\/static\/cache\//.test(item.image)) continue;

    const og = await getOgImage(link);
    if (!og) continue;

    const key  = hashName(link + '|' + og);
    const rel  = `/static/cache/${key}.jpg`;
    const dest = path.join(CACHE_DIR, `${key}.jpg`);

    try {
      await downloadThumb(og, dest);
      item.image = rel; // rewrite to local cached thumbnail
      changed = true;
      console.log('cached:', link, '->', rel);
    } catch (e) {
      console.log('skip (download error):', link);
    }
  }

  if (changed) {
    if (Array.isArray(data)) {
      // In case your file is the array form
      writeJSON(ITEMS_PATH, items);
    } else {
      data.items = items;
      writeJSON(ITEMS_PATH, data);
    }
    console.log('Updated items with cached thumbnails.');
  } else {
    console.log('No changes.');
  }
})();