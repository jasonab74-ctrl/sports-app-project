import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';

const ITEMS_PATH = 'static/teams/purdue-mbb/items.json';
const CACHE_DIR  = 'static/cache';

fs.mkdirSync(CACHE_DIR, { recursive: true });

/* ---------- helpers ---------- */
function slugify(s='') {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'').slice(0,80) || 'thumb';
}
function chooseFilename(item) {
  // Title-based to stay in lockstep with build-ssr.mjs
  return `${slugify(item.title || item.link || item.source || 'thumb')}-thumb.jpg`;
}
function absURL(base, maybeRelative) {
  try {
    return new URL(maybeRelative, base).toString();
  } catch {
    return null;
  }
}
function isYouTube(u='') {
  try {
    const h = new URL(u).hostname;
    return /(^|\.)youtube\.com$|(^|\.)youtu\.be$/.test(h);
  } catch { return false; }
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

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';

async function fetchText(url, timeoutMs=12000) {
  const ctrl = new AbortController();
  const t = setTimeout(()=>ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal, redirect: 'follow', headers: { 'User-Agent': UA, 'Accept': 'text/html,*/*' } });
    if (!r.ok) return null;
    return await r.text();
  } catch { return null; }
  finally { clearTimeout(t); }
}

async function fetchBuffer(url, timeoutMs=20000) {
  const ctrl = new AbortController();
  const t = setTimeout(()=>ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal, redirect: 'follow', headers: { 'User-Agent': UA, 'Accept': 'image/*,*/*' } });
    if (!r.ok) return null;
    const buf = Buffer.from(await r.arrayBuffer());
    // Avoid saving tiny blanks (tracking pixels, etc.)
    if (buf.length < 1024) return null;
    return buf;
  } catch { return null; }
  finally { clearTimeout(t); }
}

function extractOgImages(html='') {
  // Capture multiple possible meta variants and take the first good one
  const metas = [];
  const pushMeta = (re, idx=1) => {
    const m = re.exec(html);
    if (m && m[idx]) metas.push(m[idx]);
  };
  // common og / secure / twitter patterns
  pushMeta(/<meta[^>]+property=["']og:image:secure_url["'][^>]*content=["']([^"']+)["'][^>]*>/i);
  pushMeta(/<meta[^>]+property=["']og:image["'][^>]*content=["']([^"']+)["'][^>]*>/i);
  pushMeta(/<meta[^>]+name=["']twitter:image:src["'][^>]*content=["']([^"']+)["'][^>]*>/i);
  pushMeta(/<meta[^>]+name=["']twitter:image["'][^>]*content=["']([^"']+)["'][^>]*>/i);
  // Some sites use data-src on <meta> (rare), grab generously
  pushMeta(/<meta[^>]+content=["']([^"']+\.(?:jpg|jpeg|png|webp)(?:\?[^"']*)?)["'][^>]*>/i);
  return metas.filter(Boolean);
}

function looksImageURL(u='') {
  // Be permissive: allow missing extensions; many CDNs use querypaths.
  if (!u) return false;
  // Disallow obvious placeholders
  const s = u.toLowerCase();
  if (/sprite|placeholder|spacer|blank|default/.test(s)) return false;
  // If it has a valid image ext or data param, great
  if (/\.(jpg|jpeg|png|webp)(\?|$)/.test(s)) return true;
  // Otherwise allow; we'll validate by fetching bytes (>1KB)
  return /^https?:\/\//.test(s);
}

/* ---------- main ---------- */
async function resolveImageURL(item) {
  // 1) If item.image looks usable, start with that
  if (looksImageURL(item.image)) return item.image;

  // 2) YouTube direct thumb
  if (item.link && isYouTube(item.link)) {
    const yt = ytThumb(item.link);
    if (yt) return yt;
  }

  // 3) Scrape article page for og/twitter images
  if (item.link) {
    const html = await fetchText(item.link);
    if (html) {
      const candidates = extractOgImages(html)
        .map(u => absURL(item.link, u))
        .filter(Boolean)
        .filter(looksImageURL);
      if (candidates.length) return candidates[0];
    }
  }

  // 4) Nothing reliable
  return null;
}

async function run() {
  const raw = JSON.parse(fs.readFileSync(ITEMS_PATH, 'utf8'));
  const items = raw.items || raw || [];
  if (!Array.isArray(items) || !items.length) {
    console.log('No items to process');
    return;
  }

  for (const item of items) {
    const outName = chooseFilename(item);
    const outPath = path.join(CACHE_DIR, outName);

    // Skip if already cached
    if (fs.existsSync(outPath)) { console.log('cached (skip)', outName); continue; }

    try {
      const src = await resolveImageURL(item);
      if (!src) { console.log('no-image', item.title || item.link); continue; }

      const buf = await fetchBuffer(src);
      if (!buf) { console.log('download-failed', src); continue; }

      fs.writeFileSync(outPath, buf);
      console.log('cached', outName);
    } catch (e) {
      console.log('error', item.title || item.link, e?.message || e);
    }
  }
}

run();