import fs from 'fs';

function check(path, expectArray = false, expectKey = null) {
  if (!fs.existsSync(path)) {
    throw new Error(`Missing file: ${path}`);
  }
  const raw = fs.readFileSync(path, 'utf8');
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error(`Invalid JSON: ${path}`);
  }
  if (expectArray && !Array.isArray(data)) {
    throw new Error(`Expected array in ${path}`);
  }
  if (expectKey && !data[expectKey]) {
    throw new Error(`Missing key "${expectKey}" in ${path}`);
  }
  if (Array.isArray(data) && data.length === 0) {
    throw new Error(`Empty array in ${path}`);
  }
  if (typeof data === 'object' && !Array.isArray(data) && Object.keys(data).length === 0) {
    throw new Error(`Empty object in ${path}`);
  }
  console.log(`OK: ${path}`);
}

try {
  check('static/teams/purdue-mbb/items.json', false, 'items');
  check('static/widgets.json');
  check('static/schedule.json', true);
  check('static/insiders.json', true);
  console.log('✅ All data files valid');
} catch (e) {
  console.error('❌ Data lint failed:', e.message);
  process.exit(1);
}