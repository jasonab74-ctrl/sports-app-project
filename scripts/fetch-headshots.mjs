/**
 * Sync Purdue MBB headshots from the official roster page.
 * - Token-based name matching (robust to middle names / punctuation / casing).
 * - Multiple selector patterns (img alt=, figure+caption, data attributes).
 * - Writes JPG (and WebP if sharp present) to static/roster/<slug>.*
 * - Updates static/teams/purdue-mbb/roster.json headshot fields to local paths.
 */
import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';

let sharp = null;
try { sharp = (await import('sharp')).default; } catch { /* optional */ }

const ROSTER_JSON = 'static/teams/purdue-mbb/roster.json';
const OUT_DIR     = 'static/roster';
const SOURCE_URL  = 'https://purduesports.com/sports/mens-basketball/roster';

/* ---------------- helpers ---------------- */
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function readJSON(p, fallback) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return fallback; }
}

function normTokens(name='') {
  return String(name)
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'') // strip accents
    .toLowerCase()
    .replace(/[^a-z\s]/g,' ')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function nameKeyTokens(playerName='') {
  const t = normTokens(playerName);
  if (!t.length) return null;
  const last = t[t.length - 1];
  const first = t[0];
  const firstInit = first ? first[0] : '';
  return { first, firstInit, last };
}

function tokensMatch(player, candidate) {
  // Require last name to match, and either full first name OR first initial to match.
  if (!player || !candidate) return false;
  if (player.last !== candidate.last) return false;
  if (player.first === candidate.first) return true;
  if (player.firstInit && player.firstInit === candidate.firstInit) return true;
  return false;
}

function slugify(s='') {
  return s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'') || 'player';
}

async function fetchHTML(url) {
  const r = await fetch(url, {
    headers: {
      'user-agent': 'Mozilla/5.0 (compatible; HeadshotSync/1.1)',
      'accept': 'text/html,*/*'
    },
    redirect: 'follow'
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.text();
}

function absURL(base, u) {
  try { return new URL(u, base).toString(); } catch { return null; }
}

function extractCandidates(html) {
  const out = []; // { name, url }
  // Pattern A: <img ... alt="Full Name" src="...">
  const reAlt = /<img[^>]+alt=["']([^"']{3,60})["'][^>]*src=["']([^"']+\.(?:jpg|jpeg|png))["'][^>]*>/ig;
  let m;
  while ((m = reAlt.exec(html))) {
    out.push({ name: m[1], url: m[2] });
  }

  // Pattern B: figure + caption/name nearby
  const reFigure = /<figure[^>]*>[\s\S]*?<img[^>]*src=["']([^"']+\.(?:jpg|jpeg|png))["'][\s\S]*?<\/figure>[\s\S]*?(?:<figcaption[^>]*>|<h[1-6][^>]*>|<span[^>]*>|<a[^>]*>)([^<]{3,60})<\/(?:figcaption|h[1-6]|span|a)>/ig;
  while ((m = reFigure.exec(html))) {
    out.push({ name: m[2], url: m[1] });
  }

  // Pattern C: data-src or srcset with alt
  const reData = /<img[^>]+alt=["']([^"']{3,60})["'][^>]*(?:data-src|data-fallback|srcset|src)=["']([^"']+\.(?:jpg|jpeg|png)[^"']*)["'][^>]*>/ig;
  while ((m = reData.exec(html))) {
    // pick the first URL in srcset if present
    const src = String(m[2]).split(/\s+/)[0];
    out.push({ name: m[1], url: src });
  }

  // normalize URLs
  return out
    .filter(c => c.name && c.url)
    .map(c => ({ name: c.name.trim(), url: absURL(SOURCE_URL, c.url) }))
    .filter(c => !!c.url);
}

async function download(fileBase, url) {
  try {
    const r = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0' }, redirect: 'follow' });
    if (!r.ok) return false;
    const buf = Buffer.from(await r.arrayBuffer());
    if (buf.length < 1024) return false;

    const jpg = `${fileBase}.jpg`;
    fs.writeFileSync(jpg, buf);

    if (sharp) {
      // Normalize to 600x800 portrait, generate webp too
      await sharp(buf).resize(600, 800, { fit: 'cover', position: 'attention' })
        .jpeg({ quality: 84, mozjpeg: true }).toFile(jpg);
      await sharp(buf).resize(600, 800, { fit: 'cover', position: 'attention' })
        .webp({ quality: 84 }).toFile(`${fileBase}.webp`);
    }
    return true;
  } catch {
    return false;
  }
}

/* ---------------- main ---------------- */
async function run() {
  const roster = readJSON(ROSTER_JSON, []);
  if (!Array.isArray(roster) || roster.length === 0) {
    console.log('No roster.json or it is empty; skipping headshot sync.');
    return;
  }

  let html = '';
  try { html = await fetchHTML(SOURCE_URL); }
  catch (e) { console.log('Headshots: failed to fetch roster page:', e.message || e); return; }

  const candidates = extractCandidates(html);
  if (!candidates.length) { console.log('Headshots: no candidates parsed.'); return; }

  // Build candidate keys
  const candKeys = candidates.map(c => ({ ...c, key: nameKeyTokens(c.name) })).filter(c => c.key);

  fs.mkdirSync(OUT_DIR, { recursive: true });
  let updated = 0;

  for (const p of roster) {
    if ((p.headshot || '').trim()) continue; // already set
    const key = nameKeyTokens(p.name);
    if (!key) continue;

    // Try exact last name + first/initial match
    let c = candKeys.find(x => tokensMatch(key, x.key));

    // Fallback: last-name only match with same height bucket (if in name string)
    if (!c) {
      const last = key.last;
      const candidatesLast = candKeys.filter(x => x.key.last === last);
      if (candidatesLast.length === 1) c = candidatesLast[0];
    }

    if (!c) continue;

    const base = path.join(OUT_DIR, slugify(p.name));
    const ok = await download(base, c.url);
    if (!ok) continue;

    const webp = `${base}.webp`;
    const jpg  = `${base}.jpg`;
    p.headshot = fs.existsSync(webp) ? webp : jpg;
    updated++;

    // polite backoff to be nice to the origin
    await sleep(300);
  }

  if (updated > 0) {
    fs.writeFileSync(ROSTER_JSON, JSON.stringify(roster, null, 2));
    console.log(`Headshots: updated ${updated} players.`);
  } else {
    console.log('Headshots: no updates (names may already have headshots or parsing didn\'t match).');
  }
}

run();