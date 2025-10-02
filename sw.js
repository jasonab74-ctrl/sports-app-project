// sw.js — network-first for app shell & JSON, cache-first for images/icons
const VERSION = 'v1.0.0';
const STATIC_CACHE = `static-${VERSION}`;
const IMG_CACHE = `img-${VERSION}`;

self.addEventListener('install', (event) => {
  // Take control ASAP
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // Clear old caches
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter(k => ![STATIC_CACHE, IMG_CACHE].includes(k))
        .map(k => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

// Helpers to classify requests
const isHTML = (req) =>
  req.destination === 'document' ||
  req.headers.get('accept')?.includes('text/html');

const isJS   = (req) => req.destination === 'script';
const isCSS  = (req) => req.destination === 'style';
const isJSON = (req) =>
  req.url.includes('/static/') && req.url.endsWith('.json');
const isIMG  = (req) =>
  req.destination === 'image' || /\/(img|icons|logos)\//.test(req.url);

// Routing
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  // Network-first for app shell & data
  if (isHTML(req) || isJS(req) || isCSS(req) || isJSON(req)) {
    event.respondWith(networkFirst(req, STATIC_CACHE));
    return;
  }

  // Cache-first for images
  if (isIMG(req)) {
    event.respondWith(cacheFirst(req, IMG_CACHE));
    return;
  }

  // Otherwise: default (let the browser handle it)
});

async function networkFirst(request, cacheName) {
  try {
    const fresh = await fetch(request);
    const cache = await caches.open(cacheName);
    cache.put(request, fresh.clone());
    return fresh;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;

    if (isHTML(request)) {
      return new Response(
        '<!doctype html><meta charset="utf-8"><title>Offline</title><h1>Offline</h1>',
        { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
      );
    }
    return new Response('', { status: 503 });
  }
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const fresh = await fetch(request);
  const cache = await caches.open(cacheName);
  cache.put(request, fresh.clone());
  return fresh;
}
