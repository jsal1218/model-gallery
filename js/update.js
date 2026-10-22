// Service-worker auto-update (simplified from Avata's js/update.js). VERSION is stamped by the pre-commit hook; do not edit by hand.
// - registers sw.js with updateViaCache:'none' and checks for a new version on load, on return to the foreground and every 60 s;
// - sw.js uses skipWaiting + clients.claim, so a new deploy takes control within seconds (controllerchange);
// - then the page reloads (the hash deep link, e.g. #exact-5/base/315, is kept). Loop guard: at most 2 auto-reloads per new
//   version and 5 per minute; never for a worker whose version this page already runs.
(function () {
  const VERSION = '2026.10.22-060323-4c84b2c';
  window.__mgVersion = VERSION;
  if (!('serviceWorker' in navigator) || !location.protocol.startsWith('http')) return;
  const sw = navigator.serviceWorker, LOOP_KEY = 'mg.swReloads';
  let firstClaim = !sw.controller, reloading = false;
  function canAutoReload(target) {
    try {
      const now = Date.now(), log = JSON.parse(sessionStorage.getItem(LOOP_KEY) || '[]').filter(x => now - x.t < 600e3);
      if (target && log.filter(x => x.v === target).length >= 2) return false;
      if (log.filter(x => now - x.t < 60e3).length >= 5) return false;
      log.push({ t: now, v: target || '' }); sessionStorage.setItem(LOOP_KEY, JSON.stringify(log));
    } catch (e) {}
    return true;
  }
  const controllerVersion = () => new Promise(res => {
    const c = sw.controller; if (!c) return res('');
    const ch = new MessageChannel(); const to = setTimeout(() => res(''), 1500);
    ch.port1.onmessage = e => { clearTimeout(to); res(String((e.data && e.data.version) || '')); };
    try { c.postMessage({ type: 'version' }, [ch.port2]); } catch (e) { clearTimeout(to); res(''); }
  });
  sw.addEventListener('controllerchange', async () => {
    if (reloading) return;
    if (firstClaim) { firstClaim = false; return; }          // first install: this page already runs the latest code
    const v = await controllerVersion();
    if (v && v === VERSION) return;                           // network-first already served this page the new files
    if (!canAutoReload(v)) return;
    reloading = true; location.reload();
  });
  let reg = null, last = 0;
  const check = force => { if (!reg || (!force && Date.now() - last < 5000)) return; last = Date.now(); reg.update().catch(() => {}); };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  addEventListener('pageshow', () => check());
  addEventListener('focus', () => check());
  setInterval(() => { if (!document.hidden) check(true); }, 60e3);
  sw.register('sw.js', { updateViaCache: 'none' }).then(r => { reg = r; check(true); }).catch(() => {});
})();
