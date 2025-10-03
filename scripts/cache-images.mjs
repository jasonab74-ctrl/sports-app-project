import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';

const items = JSON.parse(fs.readFileSync('static/teams/purdue-mbb/items.json','utf8')).items || [];
const CACHE = 'static/cache';
fs.mkdirSync(CACHE,{recursive:true});

for(const it of items){
  const src = it.image;
  if(!src) continue;
  try{
    const res = await fetch(src);
    if(!res.ok) continue;
    const buf = Buffer.from(await res.arrayBuffer());
    const fname = (it.source||'src').toLowerCase().replace(/[^a-z0-9]+/g,'-')+'-thumb.jpg';
    fs.writeFileSync(path.join(CACHE,fname), buf);
    console.log('cached',fname);
  }catch(e){ console.log('fail',it.source); }
}