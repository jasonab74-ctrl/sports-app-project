/* sw.js — tombstone/cleanup worker
   Purpose: nuke any previously cached assets or JSON and then remove ourselves.
*/
self.addEventListener('install', (event) => {
  // Claim immediately so we can clean caches right away
  self.skipWaiting();
  event.waitUntil((async () => {
    // Delete ALL caches, regardless of name
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // Extra safety: delete caches again on activate
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));

    // Try to unregister ourselves so the app goes back to network-default
    try {
      const reg = await self.registration.unregister();
    } catch (_) {}
    // Take control of clients so users get a clean page without a second reload
    try { await self.clients.claim(); } catch (_) {}
  })());
});

// No fetch handler -> browser default network behavior (no SW caching)
