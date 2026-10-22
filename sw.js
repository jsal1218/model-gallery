// Avata (model gallery) service worker. VERSION is stamped automatically by the pre-commit hook (.githooks/pre-commit). Do not edit by hand.
// Strategy (same as Avata's sw.js): same-origin HTML/JS/CSS/JSON/manifest are network-first (revalidated against the server,
// cache only as the offline fallback) so a new deploy is never served stale; images are cache-first in their own cache
// (frame URLs carry ?v=, so a rebuilt frame is a new URL). skipWaiting + clients.claim, so a new version takes over at once;
// js/update.js then reloads the page.
const VERSION = '2026.10.22-065346-d9072b8';
const CACHE = `mg-${VERSION}`, IMG = 'mg-img', IMG_MAX = 600;
const SHELL = ['./', 'index.html', 'css/style.css', 'js/app.js', 'js/update.js', 'data/manifest.json', 'manifest.webmanifest',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png', 'icons/favicon-64.png'];
// cache:'reload' bypasses the HTTP cache (GitHub Pages sends max-age=600) so a new version never precaches old files
self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: 'reload' }))))); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('mg-') && k !== CACHE && k !== IMG).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('message', e => { if (e.data?.type === 'version') e.ports[0]?.postMessage({ version: VERSION }); });

const FRESH = /(\/|\.(html?|m?js|css|json|webmanifest|svg|txt))$/i;
const keep = (name, req, res) => { if (res.ok && res.type === 'basic') { const c = res.clone(); caches.open(name).then(x => x.put(req, c)); } return res; };
// keep the image cache bounded: drop the oldest entries beyond IMG_MAX
const trim = () => caches.open(IMG).then(c => c.keys().then(ks => Promise.all(ks.slice(0, Math.max(0, ks.length - IMG_MAX)).map(k => c.delete(k)))));
self.addEventListener('fetch', e => {
  const req = e.request; const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (req.mode === 'navigate' || FRESH.test(url.pathname)) {
    // network-first; 'no-cache' revalidates with the server (cheap 304s) instead of trusting the 10-minute HTTP cache
    e.respondWith(fetch(req, { cache: 'no-cache' }).then(r => keep(CACHE, req, r)).catch(async () =>
      (await caches.match(req, { ignoreSearch: true })) || (req.mode === 'navigate' ? caches.match('index.html') : Response.error())));
    return;
  }
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => { const out = keep(IMG, req, r); if (r.ok) e.waitUntil(trim()); return out; })));
});
