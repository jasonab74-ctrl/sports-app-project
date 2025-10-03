// Cloudflare Worker: strict, whitelisted image proxy with caching.
// Deploy in Cloudflare → Workers → Create → paste this file → Deploy.
// You will get a URL like: https://<your-subdomain>.workers.dev
export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      const target = url.searchParams.get('u');
      if (!target) return new Response('Missing u', { status: 400 });

      const ALLOW = [
        'img.si.com', 'si.com',
        'gannett-cdn.com', 'jconline.com',
        's.yimg.com', 'yimg.com', 'yahoo.com',
        '247sports.imgix.net', '247sports.com',
        'rivalscdn.com', 'rivals.com',
        'sportshqimages.cbsimg.net', 'cbssports.com',
        'vox-cdn.com', 'sbnation.com',
        'espncdn.com', 'espn.com',
        'apnews.com',
        'nbcsports.com', 'nbcsportsedge.com',
        'purduesports.com',
        'i.ytimg.com', 'ytimg.com', 'youtube.com'
      ];

      let t;
      try { t = new URL(target); } catch { return new Response('Bad URL', { status: 400 }); }
      const host = t.host.toLowerCase();
      const allowed = ALLOW.some(h => host === h || host.endsWith(`.${h}`));
      if (!allowed) return new Response('Host not allowed', { status: 403 });

      const headers = new Headers({
        'User-Agent': 'Mozilla/5.0 (ArtworkProxy/1.0)',
        'Accept': 'image/avif,image/webp,image/*;q=0.8,*/*;q=0.5',
        'Referer': `${t.protocol}//${t.host}/`,
      });

      const cache = caches.default;
      const cacheKey = new Request(t.toString(), { headers });
      let resp = await cache.match(cacheKey);
      if (!resp) {
        const upstream = await fetch(t.toString(), {
          headers,
          cf: { cacheTtl: 86400, cacheEverything: true }
        });
        if (!upstream.ok) return new Response('Upstream error', { status: upstream.status });

        const ct = upstream.headers.get('content-type') || '';
        if (!/^image\//i.test(ct)) return new Response('Not image', { status: 415 });

        resp = new Response(upstream.body, {
          status: 200,
          headers: {
            'Content-Type': ct,
            'Cache-Control': 'public, max-age=86400',
            'Access-Control-Allow-Origin': '*'
          }
        });
        ctx.waitUntil(cache.put(cacheKey, resp.clone()));
      }
      return resp;
    } catch {
      return new Response('Proxy error', { status: 500 });
    }
  }
}