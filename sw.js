// Self-destructing service worker.
// Takes control immediately, wipes caches, then unregisters itself.

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    } catch (e) {}
    try {
      await self.clients.claim();
      await self.registration.unregister();
    } catch (e) {}
  })());
});

// Pass-through; we don’t cache anything here.
self.addEventListener('fetch', () => {});