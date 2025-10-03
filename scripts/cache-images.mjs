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
const CACHE_DIR = path.join(ROOT, 'static', 'cache');

const OFFICIAL_HOSTS = new Set([
  'purduesports.com',
  'youtube.com', 'youtu.be',
  'jconline.com',
  'hammerandrails.com',
  'sbnation.com',
]);

// Helper: read & write JSON safely
const readJSON = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const writeJSON = (p, obj) => fs.writeFileSync(p, JSON.stringify(obj, null, 2));

// Ensure cache dir
fs.mkdirSync(CACHE_DIR, { recursive: true });

function etld1(host) {
  if (!host) return '';
  const parts = host.toLowerCase().split('.').filter(Boolean);
  if (parts.length <= 2) return host.toLowerCase();
  return parts.slice(-2).join('.');
}

function shouldCache(urlStr) {
  try {
    const u = new URL(urlStr);
    const host = etld1(u.host);
    if (process.env.OFFICIAL_ONLY) {
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
        'Accept': 'text/html,application/xhtml+xml',
      },
      redirect: 'follow',
      timeout: 15000
    });
    if (!res.ok) return null;
    const html = await res.text();
    const dom = new JSDOM(html);
    const doc = dom.window.document;
    const og = doc.querySelector('meta[property="og:image"], meta[name="og:image"]');
    if (og?.content) return new URL(og.content, link).toString();

    // Try twitter image as fallback
    const tw = doc.querySelector('meta[name="twitter:image"], meta[property="twitter:image"]');
    if (tw?.content) return new URL(tw.content, link).toString();

    return null;
  } catch {
    return null;
  }
}

async function downloadThumb(src, destPath) {
  const res = await fetch(src, {
    headers: { 'User-Agent': 'Mozilla/5.0 (ArtCacheBot/1.0)' },
    redirect: 'follow',
    timeout: 20000
  });
  if (!res.ok) throw new Error('bad fetch ' + res.status);
  const buf = Buffer.from(await res.arrayBuffer());
  const out = await sharp(buf).resize({ width: 800, withoutEnlargement: true }).jpeg({ quality: 78 }).toBuffer();
  fs.writeFileSync(destPath, out);
}

function hashName(str) {
  // simple stable hash
  let h = 0; for (let i = 0; i < str.length; i++) { h = (h * 33) ^ str.charCodeAt(i); }
  return (h >>> 0).toString(16);
}

(async function main() {
  const data = readJSON(ITEMS_PATH);
  const items = data.items || data;

  let changed = false;

  for (const item of items) {
    const link = item.link;
    if (!link || !shouldCache(link)) continue;

    // Skip if we already cached
    if (item.image && item.image.startsWith('/static/cache/')) continue;

    const og = await getOgImage(link);
    if (!og) continue;

    const key = hashName(link + '|' + og);
    const rel = `/static/cache/${key}.jpg`;
    const dest = path.join(ROOT, 'static', 'cache', `${key}.jpg`);

    try {
      await downloadThumb(og, dest);
      item.image = rel; // rewrite to local cached thumbnail
      changed = true;
      console.log('cached:', link, '->', rel);
    } catch (e) {
      console.log('skip (dl err):', link);
    }
  }

  if (changed) {
    if (data.items) data.items = items;
    writeJSON(ITEMS_PATH, data);
  } else {
    console.log('no changes');
  }
})();