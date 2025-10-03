// One-time service-worker cleanup for GitHub Pages scope.
// Registers a self-destructing sw.js, waits for it to take control,
// then unregisters ALL SWs and clears ALL caches for this origin.
(async () => {
  if (!('serviceWorker' in navigator)) return;

  try {
    // Compute repo root scope (e.g., /sports-app-project/)
    const root = location.pathname.replace(/\/[^/]*$/, '/') || '/';
    const swUrl = root + 'sw.js';

    // Register killer SW at the site scope
    const reg = await navigator.serviceWorker.register(swUrl, { scope: root });
    await navigator.serviceWorker.ready;

    // Unregister all service workers
    const regs = await navigator.serviceWorker.getRegistrations();
    for (const r of regs) {
      try { await r.unregister(); } catch (e) {}
    }

    // Clear all caches
    if (window.caches) {
      const keys = await caches.keys();
      await Promise.all(keys.map(k => caches.delete(k)));
    }

    // Optional: reload once to ensure the page is now uncontrolled
    // location.reload();
    console.log('[SW-KILL] Old service workers and caches cleared.');
  } catch (e) {
    console.log('[SW-KILL] Cleanup error:', e);
  }
})();