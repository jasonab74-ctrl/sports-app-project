import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';

const ITEMS_PATH = 'static/teams/purdue-mbb/items.json';
const CACHE_DIR  = 'static/cache';

fs.mkdirSync(CACHE_DIR, { recursive: true });

function slugify(s='') {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'').slice(0,80) || 'thumb';
}
function isYouTube(u='') {
  return /(^|\.)youtube\.com$|(^|\.)youtu\.be$/.test(new URL(u).hostname);
}
function ytId(u='') {
  try {
    const url = new URL(u);
    if (url.hostname.includes('youtu.be')) return url.pathname.slice(1);
    if (url.searchParams.get('v')) return url.searchParams.get('v');
    const m = /\/embed\/([^?]+)/.exec(url.pathname);
    return m ? m[1] : null;
  } catch { return null; }
}
function ytThumb(u) {
  const id = ytId(u);
  return id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : null;
}
function isLikelyBadImage(src='') {
  const s = src.toLowerCase();
  if (!s) return true;
  if (/(sprite|logo|placeholder|default|blank|spacer)\.(png|svg|gif)$/.test(s)) return true;
  return !/\.(jpg|jpeg|png|webp)(\?|$)/.test(s);
}
async function fetchText(url, timeoutMs=10000) {
  const ctrl = new AbortController();
  const t = setTimeout(()=>ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal, redirect: 'follow' });
    if (!r.ok) return null;
    return await r.text();
  } catch { return null; }
  finally { clearTimeout(t); }
}
async function fetchBuffer(url, timeoutMs=15000) {
  const ctrl = new AbortController();
  const t = setTimeout(()=>ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal, redirect: 'follow' });
    if (!r.ok) return null;
    const ab = await r.arrayBuffer();
    const buf = Buffer.from(ab);
    // tiny/blank images are useless
    if (buf.length < 1024) return null;
    return buf;
  } catch { return null; }
  finally { clearTimeout(t); }
}
function extractOgImage(html='') {
  // OG/Twitter image scraping (simple + robust)
  const og  = html.match(/<meta[^>]+property=["']og:image["'][^>]*content=["']([^"']+)["'][^>]*>/i)?.[1];
  const tw  = html.match(/<meta[^>]+name=["']twitter:image(:src)?["'][^>]*content=["']([^"']+)["'][^>]*>/i)?.[2];
  return og || tw || null;
}
function chooseFilename(item) {
  // Key on TITLE to avoid source collisions
  const base = slugify(item.title || item.link || item.source || 'thumb');
  return `${base}-thumb.jpg`;
}

async function resolveImageURL(item) {
  // 1) Trust explicit item.image if it looks valid
  if (item.image && !isLikelyBadImage(item.image)) return item.image;

  // 2) YouTube fallback
  if (item.link && isYouTube(item.link)) {
    const yt = ytThumb(item.link);
    if (yt) return yt;
  }

  // 3) Scrape article page for OG/Twitter image
  if (item.link) {
    try {
      const html = await fetchText(item.link);
      if (html) {
        const metaImg = extractOgImage(html);
        if (metaImg && !isLikelyBadImage(metaImg)) return metaImg;
      }
    } catch {/* ignore */}
  }

  // 4) Nothing reliable
  return null;
}

async function run() {
  const json = JSON.parse(fs.readFileSync(ITEMS_PATH, 'utf8'));
  const items = json.items || json || [];
  if (!Array.isArray(items) || !items.length) {
    console.log('No items to process'); return;
  }

  for (const item of items) {
    try {
      const outName = chooseFilename(item);
      const outPath = path.join(CACHE_DIR, outName);
      // Skip if already cached
      if (fs.existsSync(outPath)) { console.log('cached (skip)', outName); continue; }

      const src = await resolveImageURL(item);
      if (!src) { console.log('no-image', item.title); continue; }

      const buf = await fetchBuffer(src);
      if (!buf) { console.log('download-failed', src); continue; }

      fs.writeFileSync(outPath, buf);
      console.log('cached', outName);
    } catch (e) {
      console.log('error', item.title, e?.message || e);
    }
  }
}

run();