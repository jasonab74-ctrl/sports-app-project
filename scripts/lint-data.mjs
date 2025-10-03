import fs from 'fs';

function isHttpUrl(u='') {
  try { const x = new URL(u); return x.protocol === 'http:' || x.protocol === 'https:'; }
  catch { return false; }
}

function check(path, expectArray = false, expectKey = null) {
  if (!fs.existsSync(path)) throw new Error(`Missing file: ${path}`);
  const raw = fs.readFileSync(path, 'utf8');
  let data;
  try { data = JSON.parse(raw); }
  catch { throw new Error(`Invalid JSON: ${path}`); }

  if (expectArray && !Array.isArray(data)) throw new Error(`Expected array in ${path}`);
  if (expectKey && !data[expectKey]) throw new Error(`Missing key "${expectKey}" in ${path}`);

  if (Array.isArray(data) && data.length === 0) throw new Error(`Empty array in ${path}`);
  if (typeof data === 'object' && !Array.isArray(data) && Object.keys(data).length === 0)
    throw new Error(`Empty object in ${path}`);

  return data;
}

try {
  // Core files exist and parse
  const itemsData = check('static/teams/purdue-mbb/items.json', false, 'items');
  const widgets   = check('static/widgets.json');
  const schedule  = check('static/schedule.json', true);
  const insiders  = check('static/insiders.json', true);

  // Item-level validation
  const items = itemsData.items || itemsData || [];
  if (!Array.isArray(items) || items.length === 0) {
    throw new Error('No items in items.json');
  }

  const titles = new Set();
  let dupCount = 0, badLink = 0, missing = 0;

  for (const [idx, it] of items.entries()) {
    const t = (it.title || '').trim();
    const l = (it.link || '').trim();

    if (!t || !l) { missing++; console.error(`Item ${idx} missing title or link`); continue; }
    if (!isHttpUrl(l)) { badLink++; console.error(`Item ${idx} has non-http(s) link: ${l}`); }

    const key = t.toLowerCase();
    if (titles.has(key)) { dupCount++; console.warn(`Duplicate title: "${t}"`); }
    titles.add(key);
  }

  if (missing > 0) throw new Error(`Found ${missing} items missing title or link`);
  if (badLink > 0) throw new Error(`Found ${badLink} items with invalid link URLs`);
  if (dupCount > 3) throw new Error(`Too many duplicate titles (${dupCount})`);

  console.log('✅ Lint passed: items/widgets/schedule/insiders look good');
} catch (e) {
  console.error('❌ Data lint failed:', e.message);
  process.exit(1);
}