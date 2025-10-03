// caches artwork from official/friendly sources
import fs from 'fs'; import path from 'path';
import fetch from 'node-fetch'; import { JSDOM } from 'jsdom'; import sharp from 'sharp';

const ROOT = process.cwd();
const TEAM = 'purdue-mbb';
const ITEMS_PATH = path.join(ROOT,'static','teams',TEAM,'items.json');
const CACHE_DIR  = path.join(ROOT,'static','cache');
const OFFICIAL = new Set(['purduesports.com','youtube.com','youtu.be','jconline.com','hammerandrails.com','sbnation.com','si.com','espn.com']);

fs.mkdirSync(CACHE_DIR,{recursive:true});
const read = p=>JSON.parse(fs.readFileSync(p,'utf8'));
const write=(p,obj)=>fs.writeFileSync(p,JSON.stringify(obj,null,2));

async function getOg(link){
  try{ const r=await fetch(link,{headers:{'User-Agent':'ArtCacheBot'}}); if(!r.ok) return null;
    const html=await r.text(); const doc=new JSDOM(html).window.document;
    const meta = doc.querySelector('meta[property="og:image"],meta[name="og:image"],meta[name="twitter:image"]');
    return meta?.content||null;
  }catch{ return null; }
}
async function thumb(src,dest){ const r=await fetch(src); if(!r.ok) throw Error(); const buf=Buffer.from(await r.arrayBuffer()); const out=await sharp(buf).resize({width:800}).jpeg({quality:78}).toBuffer(); fs.writeFileSync(dest,out); }
const hash=s=>[...s].reduce((a,c)=>(a*33)^c.charCodeAt(0),0)>>>0;

(async()=>{
  const data=read(ITEMS_PATH); const items=data.items||data; let changed=false;
  for(const item of items){
    if(!item.link) continue;
    try{ const host=new URL(item.link).host.replace(/^www\./,''); if(!OFFICIAL.has(host)) continue; }catch{}
    if(item.image?.startsWith('/static/cache/')) continue;
    const og=await getOg(item.link); if(!og) continue;
    const key=hash(item.link+og).toString(16); const rel=`/static/cache/${key}.jpg`; const dest=path.join(CACHE_DIR,`${key}.jpg`);
    try{ await thumb(og,dest); item.image=rel; changed=true; console.log('cached',item.link,'->',rel);}catch{}
  }
  if(changed){ data.items?data.items=items:items; write(ITEMS_PATH,data); console.log('Updated items.'); }
})();