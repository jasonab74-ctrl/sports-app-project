
const VERSION = 'v1.0.5';
const APP_PREFIX = 'sports-app';
const PRECACHE = [
  './',
  './index.html',
  './static/css/pro.css',
  './static/js/pro.js',
];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(`${APP_PREFIX}-${VERSION}`).then(c=>c.addAll(PRECACHE)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith(APP_PREFIX) && !k.endsWith(VERSION)).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(async () => {
        const clients = await self.clients.matchAll();
        for (const client of clients){
          client.postMessage({type:'NEW_VERSION'});
        }
      })
  );
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.includes('/static/') && url.pathname.endsWith('.json')){
    e.respondWith((async () => {
      const cacheName = `${APP_PREFIX}-json-${VERSION}`;
      const cache = await caches.open(cacheName);
      const cached = await cache.match(e.request);
      const fetchPromise = fetch(e.request).then(networkResponse => {
        cache.put(e.request, networkResponse.clone());
        return networkResponse;
      }).catch(()=>cached);
      return cached || fetchPromise;
    })());
    return;
  }
  if (PRECACHE.some(p => url.pathname.endsWith(p.replace('./','/')))){
    e.respondWith(caches.match(e.request).then(resp => resp || fetch(e.request)));
  }
});
