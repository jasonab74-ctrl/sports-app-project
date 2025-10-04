import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';

let sharp = null;
try { sharp = (await import('sharp')).default; } catch { /* optional */ }

const ROSTER_JSON = 'static/teams/purdue-mbb/roster.json';
const OUT_DIR = 'static/roster';
const SOURCE_URL = 'https://purduesports.com/sports/mens-basketball/roster';

fs.mkdirSync(OUT_DIR, { recursive: true });

function normName(s='') {
  return s.toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'') // strip accents
    .replace(/[^a-z\s]/g,'')
    .replace(/\s+/g,' ')
    .trim();
}
function slugify(s='') {
  return s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'') || 'player';
}

async function fetchHTML(url) {
  const r = await fetch(url, {
    headers: {
      'user-agent': 'Mozilla/5.0 (compatible; HeadshotSync/1.0)',
      'accept': 'text/html,*/*'
    },
    redirect: 'follow'
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.text();
}

function parseHeadshots(html) {
  // Very forgiving: look for a player name near an <img> tag on the roster page.
  // Pattern 1: <img ... alt="Name" src="...">
  // Pattern 2: <img ... src="..."><...>Name</...
  const out = new Map();

  // Collect all <img ... alt="..."> first
  const imgAltRe = /<img[^>]+alt=["']([^"']+)["'][^>]*src=["']([^"']+)["'][^>]*>/ig;
  let m;
  while ((m = imgAltRe.exec(html))) {
    const alt = m[1] || '';
    const src = m[2] || '';
    const n = normName(alt);
    if (n && src && /\.(jpg|jpeg|png)/i.test(src)) {
      out.set(n, new URL(src, SOURCE_URL).toString());
    }
  }

  // Fallback: names in a sibling text with image before
  const blockRe = /<figure[^>]*>[\s\S]*?<img[^>]*src=["']([^"']+)["'][\s\S]*?<\/figure>[\s\S]*?(?:<h\d[^>]*>|<a[^>]*>|<span[^>]*>)([^<]{3,40})<\/(?:h\d|a|span)>/ig;
  while ((m = blockRe.exec(html))) {
    const src = m[1] || '';
    const maybeName = (m[2] || '').replace(/\s+/g,' ').trim();
    const n = normName(maybeName);
    if (n && src && /\.(jpg|jpeg|png)/i.test(src) && !out.has(n)) {
      out.set(n, new URL(src, SOURCE_URL).toString());
    }
  }

  return out; // Map<normalized name, absolute URL>
}

async function downloadTo(fileBase, url) {
  try {
    const r = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0' } });
    if (!r.ok) return null;
    const buf = Buffer.from(await r.arrayBuffer());
    if (buf.length < 1024) return null;

    const jpgPath = `${fileBase}.jpg`;
    fs.writeFileSync(jpgPath, buf);

    if (sharp) {
      await sharp(buf).resize(600, 800, { fit: 'cover', position: 'attention' })
        .jpeg({ quality: 82, mozjpeg: true }).toFile(jpgPath);
      await sharp(buf).resize(600, 800, { fit: 'cover', position: 'attention' })
        .webp({ quality: 82 }).toFile(`${fileBase}.webp`);
    }

    return true;
  } catch {
    return null;
  }
}

async function run() {
  // Load roster JSON
  let roster = [];
  try { roster = JSON.parse(fs.readFileSync(ROSTER_JSON, 'utf8')); }
  catch { console.log('No roster.json found, skipping.'); return; }
  if (!Array.isArray(roster) || roster.length === 0) { console.log('Roster empty, skipping.'); return; }

  // Fetch official roster page
  let html = '';
  try { html = await fetchHTML(SOURCE_URL); }
  catch (e) {
    console.log('Failed to fetch official roster page:', e.message || e);
    return;
  }

  const headshotMap = parseHeadshots(html);
  if (!headshotMap.size) {
    console.log('No headshots parsed from official site.');
  }

  // Update players
  let changed = 0;
  for (const p of roster) {
    if ((p.headshot || '').trim()) continue; // already set

    const key = normName(p.name);
    const imgUrl = headshotMap.get(key);
    if (!imgUrl) continue;

    const base = path.join(OUT_DIR, slugify(p.name));
    const ok = await downloadTo(base, imgUrl);
    if (!ok) continue;

    // Prefer webp if generated, else jpg
    const webp = `${base}.webp`.replace(/^static\//, 'static/');
    const jpg  = `${base}.jpg`.replace(/^static\//, 'static/');
    p.headshot = fs.existsSync(webp) ? webp : jpg;
    changed++;
  }

  if (changed > 0) {
    fs.writeFileSync(ROSTER_JSON, JSON.stringify(roster, null, 2));
    console.log(`Updated ${changed} headshots in roster.json`);
  } else {
    console.log('No headshots updated (maybe all set already).');
  }
}

run();