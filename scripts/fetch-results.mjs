/**
 * Update static/schedule.json with final results for past games.
 * Source: ESPN public team schedule endpoint (team id 2509).
 *
 * Notes:
 * - We fetch both regular season (seasontype=2) and postseason (seasontype=3).
 * - For past events with a final status, we write:
 *      outcome: "W" | "L"
 *      final_score: "Purdue 78–65 Opponent"
 *      recap_url: ESPN recap link (if present)
 *      box_url: ESPN box score link (if present)
 * - Future games are left untouched.
 * - Any existing user-entered fields are preserved (we don't overwrite non-empty).
 */

import fs from 'fs';
import fetch from 'node-fetch';

const FILE = 'static/schedule.json';
const TEAM_ID = 2509; // Purdue MBB on ESPN (confirmed)
const BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball';

function readJSON(path, fallback) {
  try { return JSON.parse(fs.readFileSync(path, 'utf8')); } catch { return fallback; }
}
function writeJSON(path, data) {
  fs.mkdirSync(require('path').dirname(path), { recursive: true });
  fs.writeFileSync(path, JSON.stringify(data, null, 2));
}

async function getESPNSeason(seasonType) {
  // Add season param so we get the current season’s schedule explicitly.
  const year = new Date().getUTCFullYear(); // good enough; ESPN returns current season window
  const url = `${BASE}/teams/${TEAM_ID}/schedule?season=${year}&seasontype=${seasonType}`;
  const r = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0' } });
  if (!r.ok) throw new Error(`ESPN ${seasonType} HTTP ${r.status}`);
  return await r.json();
}

function normalizeESPN(json) {
  // ESPN shape: { events:[{ competitions:[{ competitors:[home, away], status:{type:{completed}}, date, links:[] }], shortName, id }], team:{...} }
  const out = [];
  const teamDisplay = (json?.team?.displayName || 'Purdue').toLowerCase();

  for (const ev of json?.events || []) {
    const comp = ev.competitions?.[0];
    if (!comp) continue;
    const date = comp.date || ev.date;
    const status = comp.status?.type || {};
    const completed = !!status?.completed;

    // Teams
    const home = comp.competitors?.find(c => c.homeAway === 'home');
    const away = comp.competitors?.find(c => c.homeAway === 'away');
    if (!home || !away) continue;

    const homeName = home.team?.displayName || home.team?.name || 'Home';
    const awayName = away.team?.displayName || away.team?.name || 'Away';

    const isPurdueHome = (homeName || '').toLowerCase().includes('purdue');
    const purdueSide = isPurdueHome ? home : away;
    const oppSide = isPurdueHome ? away : home;
    const opponent = oppSide.team?.displayName || oppSide.team?.name || 'Opponent';

    // Links
    let recap_url = '';
    let box_url = '';
    for (const l of comp.links || ev.links || []) {
      const href = l.href || l.uri || '';
      if (/recap/i.test(l.text || '') || /recap/.test(href)) recap_url = href;
      if (/boxscore/i.test(l.text || '') || /boxscore/.test(href)) box_url = href;
    }

    // Score + outcome if final
    let outcome = '';
    let final_score = '';

    if (completed) {
      const ps = Number(purdueSide.score?.value ?? purdueSide.score);
      const os = Number(oppSide.score?.value ?? oppSide.score);

      if (!Number.isNaN(ps) && !Number.isNaN(os)) {
        outcome = ps > os ? 'W' : (ps < os ? 'L' : '');
        // "Purdue 78–65 Opponent"
        final_score = `${isPurdueHome ? 'Purdue' : 'Purdue'} ${ps}\u2013${os} ${opponent}`;
      }
    }

    out.push({
      utc: date,                // keep ISO UTC for builder
      opp: opponent,
      site: isPurdueHome ? 'Home' : 'Away',
      espn_url: `https://www.espn.com/mens-college-basketball/matchup?gameId=${ev.id}`,
      recap_url, box_url,
      outcome, final_score,
      _completed: completed     // helper (not written to file)
    });
  }
  return out;
}

function idxKey(g) {
  // Key by (date, opp, site) to align with your schedule.json
  const d = (g.utc || g.date || '').slice(0, 10); // YYYY-MM-DD
  return `${d}|${(g.opp||'').toLowerCase()}|${(g.site||'').toLowerCase()}`;
}

function mergeIntoLocal(localArr, espnArr) {
  const map = new Map();
  for (const e of espnArr) map.set(idxKey(e), e);

  let changed = 0;
  const now = Date.now();

  for (const g of localArr) {
    const d = new Date(g.utc || g.date || '');
    if (!d || isNaN(+d)) continue;

    // Only update past games
    if (+d >= now) continue;

    const match = map.get(idxKey(g));
    if (!match || !match._completed) continue;

    // Only fill if empty; don't overwrite user-entered values
    const before = JSON.stringify({ outcome: g.outcome || '', final_score: g.final_score || '', recap_url: g.recap_url || '', box_url: g.box_url || '' });

    if (!g.outcome && match.outcome) g.outcome = match.outcome;
    if (!g.final_score && match.final_score) g.final_score = match.final_score;
    if (!g.recap_url && match.recap_url) g.recap_url = match.recap_url;
    if (!g.box_url && match.box_url) g.box_url = match.box_url;

    const after = JSON.stringify({ outcome: g.outcome || '', final_score: g.final_score || '', recap_url: g.recap_url || '', box_url: g.box_url || '' });
    if (before !== after) changed++;
  }
  return changed;
}

async function run() {
  const local = readJSON(FILE, []);
  if (!Array.isArray(local) || local.length === 0) {
    console.log('results: no local schedule.json, skipping.');
    return;
  }

  // Pull both regular season and postseason windows
  const [reg, post] = await Promise.allSettled([ getESPNSeason(2), getESPNSeason(3) ]);
  const regOK  = reg.status  === 'fulfilled' ? reg.value : null;
  const postOK = post.status === 'fulfilled' ? post.value : null;

  const espnGames = [
    ...(regOK  ? normalizeESPN(regOK)  : []),
    ...(postOK ? normalizeESPN(postOK) : [])
  ];

  if (!espnGames.length) {
    console.log('results: ESPN returned no events; nothing to merge.');
    return;
  }

  const localCopy = JSON.parse(JSON.stringify(local));
  const changed = mergeIntoLocal(localCopy, espnGames);

  if (changed > 0) {
    writeJSON(FILE, localCopy);
    console.log(`results: updated ${changed} past games with finals.`);
  } else {
    console.log('results: no updates needed.');
  }
}

run().catch(e => {
  console.error('results: failed', e?.message || e);
});