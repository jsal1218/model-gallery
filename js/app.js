/* Atelier 360 — image-sequence turnaround viewer. Plain JS, no build step. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const viewer = $('viewer'), stage = $('stage'), imgA = $('imgA'), imgB = $('imgB');
  const BLEND_GAP = 22.5;          // frame gaps wider than this crossfade between neighbours
  const MAX_BLEND_GAP = 60;        // ...but never dissolve across very sparse sets (front<->back ghosting)
  const AUTO_SPEED = 0.03;         // deg per ms (30°/s)
  const MAX_ZOOM = 5, DBL_ZOOM = 2.5, HI_AT = 1.15;

  const S = {
    manifest: null, model: null, outfit: null, frames: [],
    angle: 0, vel: 0, auto: false, lastT: 0, snapTo: null,
    zoom: 1, tx: 0, ty: 0, loaded: new Map(), hiLoaded: new Set(), token: 0,
  };

  const mod = (a, n = 360) => ((a % n) + n) % n;
  const label = (a) => { a = mod(Math.round(a));
    // frames turn so the model faces frame-left at 90 (camera sees her LEFT side) and frame-right at 270
    if (a <= 22 || a >= 338) return 'Front'; if (a < 68) return 'Front ¾ · left'; if (a <= 112) return 'Left side';
    if (a < 158) return 'Back ¾ · left'; if (a <= 202) return 'Back'; if (a < 248) return 'Back ¾ · right';
    if (a <= 292) return 'Right side'; return 'Front ¾ · right'; };

  /* ---------- data ---------- */
  async function init() {
    try {
      const res = await fetch('data/manifest.json', { cache: 'no-cache' });
      S.manifest = await res.json();
    } catch (e) { $('loaderText').textContent = 'Could not load manifest'; console.error(e); return; }
    const [h0, ho, ha] = location.hash.replace('#', '').split('/');
    const hm = (S.manifest.aliases || {})[h0] || h0;   // retired ids (#model-2 … #model-6) map to their renumbered model
    const model = S.manifest.models.find(m => m.id === hm) || S.manifest.models[0];  // unknown ids (e.g. deleted old Model 5) → Model 1
    renderModels();
    await selectModel(model.id, ho, ha !== undefined ? +ha : 0);
    // warm the cache for the other models in the background
    setTimeout(() => S.manifest.models.forEach(m => m.outfits.forEach(o => o.frames.forEach(f => { const i = new Image(); i.src = f.lo; }))), 1500);
    requestAnimationFrame(tick);
  }

  // main row = exact-reference models; models with group "photoreal" go in the separate Photorealistic row below
  function renderModels() {
    const box = $('models'), pbox = $('photoreal'); box.innerHTML = ''; pbox.innerHTML = '';
    const photo = S.manifest.models.filter(m => m.group === 'photoreal');
    pbox.hidden = $('photorealH').hidden = !photo.length;
    S.manifest.models.forEach(m => {
      const b = document.createElement('button');
      b.className = 'model'; b.type = 'button'; b.role = 'tab'; b.dataset.id = m.id;
      b.innerHTML = `<img src="${m.thumb}" alt=""><span><b>${m.name}</b><small>${m.descriptor}</small></span>`;
      b.addEventListener('click', () => selectModel(m.id));
      (m.group === 'photoreal' ? pbox : box).appendChild(b);
    });
  }

  // mobile switcher is a horizontal scroll row: bring the selected model into view (horizontal only, never scrolls the page)
  function revealModel(id) {
    const b = document.querySelector(`.model[data-id="${id}"]`), box = b && b.parentElement;
    if (!b || box.scrollWidth <= box.clientWidth + 1) return;
    const br = b.getBoundingClientRect(), xr = box.getBoundingClientRect(), padL = 14;
    if (br.left < xr.left + padL || br.right > xr.right - padL) box.scrollTo({ left: box.scrollLeft + br.left - xr.left - padL, behavior: 'smooth' });
  }

  function renderOutfits() {
    const box = $('outfits'); box.innerHTML = '';
    S.model.outfits.forEach(o => {
      const b = document.createElement('button');
      b.className = 'outfit'; b.type = 'button'; b.dataset.id = o.id;
      b.innerHTML = `<div class="ph" style="background-image:url('${o.frames[0].lo}')"></div><b>${o.name}</b><small>${o.subtitle} · ${o.frames.length} angles</small>`;
      b.addEventListener('click', () => selectOutfit(o.id, S.angle));
      box.appendChild(b);
    });
  }

  async function selectModel(id, outfitId, angle) {
    S.model = S.manifest.models.find(m => m.id === id);
    document.querySelectorAll('.model').forEach(b => b.setAttribute('aria-selected', b.dataset.id === id));
    revealModel(id);
    renderOutfits();
    await selectOutfit((S.model.outfits.find(o => o.id === outfitId) || S.model.outfits[0]).id, angle ?? S.angle);
  }

  async function selectOutfit(id, angle) {
    S.outfit = S.model.outfits.find(o => o.id === id);
    S.frames = [...S.outfit.frames].sort((a, b) => a.angle - b.angle);
    document.querySelectorAll('.outfit').forEach(b => b.setAttribute('aria-current', b.dataset.id === id));
    resetZoom(true);
    S.angle = mod(angle || 0); S.vel = 0; S.snapTo = null;
    $('metaLine').textContent = `${S.model.name} · ${S.outfit.name} · ${S.frames.length} angles`;
    buildDial(); buildQuick(); setNote();
    await preload(S.frames);
    render(true);
    updateHash();
  }

  function preload(frames) {
    const token = ++S.token, loader = $('loader');
    let done = 0; const total = frames.length;
    const need = frames.filter(f => !S.loaded.has(f.lo));
    if (!need.length) { loader.classList.add('done'); return Promise.resolve(); }
    loader.classList.remove('done');
    done = total - need.length;
    const upd = () => { $('loaderBar').style.width = (100 * done / total) + '%'; $('loaderText').textContent = `Loading ${done} / ${total} angles`; };
    upd();
    return Promise.all(need.map(f => new Promise(res => {
      const i = new Image();
      i.onload = () => { (i.decode ? i.decode() : Promise.resolve()).catch(() => {}).then(() => { S.loaded.set(f.lo, i); done++; if (token === S.token) upd(); res(); }); };
      i.onerror = () => { console.warn('frame failed', f.lo); done++; res(); };
      i.src = f.lo;
    }))).then(() => { if (token === S.token) setTimeout(() => loader.classList.add('done'), 120); });
  }

  /* ---------- rendering ---------- */
  function bracket(a) {
    const F = S.frames, n = F.length;
    if (n === 1) return { p: F[0], q: F[0], t: 0, gap: 360 };
    let i = n - 1;
    for (let k = 0; k < n; k++) if (F[k].angle <= a) i = k;
    const p = F[i], q = F[(i + 1) % n];
    const gap = mod(q.angle - p.angle) || 360;
    return { p, q, t: mod(a - p.angle) / gap, gap };
  }
  const smooth = (x) => x * x * (3 - 2 * x);
  const srcFor = (f) => (S.zoom > HI_AT && S.hiLoaded.has(f.hi)) ? f.hi : f.lo;

  let lastKey = '';
  function render(force) {
    const a = S.angle, { p, q, t, gap } = bracket(a);
    let A = p, B = q, w;
    if (gap <= BLEND_GAP || gap > MAX_BLEND_GAP) { A = t < 0.5 ? p : q; w = 0; }
    else w = smooth(Math.min(1, Math.max(0, (t - 0.4) / 0.2)));    // hold, short dissolve around the midpoint, hold
    if (S.zoom > 1.001) { A = w < 0.5 ? A : B; w = 0; }              // no ghosting while inspecting detail
    const sa = srcFor(A), sb = srcFor(B);
    const key = sa + '|' + sb + '|' + w.toFixed(3);
    if (force || key !== lastKey) {
      if (imgA.getAttribute('src') !== sa) imgA.src = sa;
      if (w > 0) { if (imgB.getAttribute('src') !== sb) imgB.src = sb; imgB.style.opacity = w; imgA.style.opacity = 1; }
      else imgB.style.opacity = 0;
      lastKey = key;
      imgA.alt = `${S.model.name}, ${S.outfit.subtitle}, ${label(a)} view`;
    }
    const d = Math.round(mod(a)) % 360;
    $('angleVal').textContent = d + '°';
    $('angleLabel').textContent = label(a);
    $('dialHand').style.transform = `rotate(${a}deg)`;
    document.querySelectorAll('.quick button').forEach(b => b.classList.toggle('on', Math.abs(mod(+b.dataset.a - a + 180) - 180) < 10));
  }

  function buildDial() {
    const g = $('dialTicks'); g.innerHTML = '';
    S.frames.forEach(f => {
      const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      l.setAttribute('x1', 32); l.setAttribute('y1', 2.5); l.setAttribute('x2', 32); l.setAttribute('y2', 6);
      l.setAttribute('class', 'tick has'); l.setAttribute('transform', `rotate(${f.angle} 32 32)`); g.appendChild(l);
    });
  }
  function buildQuick() {
    const box = $('quickAngles'); box.innerHTML = '';
    [['Front', 0], ['¾', 45], ['Side', 90], ['Back', 180]].forEach(([n, a]) => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = n; b.dataset.a = a;
      b.addEventListener('click', () => { stopAuto(); resetZoom(); goTo(a); });
      box.appendChild(b);
    });
  }
  function setNote() {
    const n = S.frames.length, refs = S.frames.filter(f => f.source === 'reference').length;
    $('note').textContent = n < 8
      ? `Preview set: ${n} photographed angles${refs ? ' (front & back reference)' : ''}. In-between angles show the nearest photographed view until the full turnaround frames are added.`
      : `${n}-angle turnaround${refs ? `, ${refs} from original reference photos` : ''}. Zoom swaps in ${S.manifest.canvas.hi[1]}px frames.`;
  }

  /* ---------- motion loop ---------- */
  function nearestFrameAngle(a) {
    let best = S.frames[0].angle, bd = 999;
    S.frames.forEach(f => { const d = Math.abs(mod(f.angle - a + 180) - 180); if (d < bd) { bd = d; best = f.angle; } });
    return best;
  }
  function goTo(a) { S.vel = 0; S.snapTo = a; }
  function tick(now) {
    const dt = Math.min(48, now - (S.lastT || now)); S.lastT = now;
    if (S.frames.length) {
      if (S.auto && !drag.active) S.angle = mod(S.angle + AUTO_SPEED * dt);
      else if (Math.abs(S.vel) > 0.004 && !drag.active) {
        S.angle = mod(S.angle + S.vel * dt);
        S.vel *= Math.pow(0.94, dt / 16.7);
        if (Math.abs(S.vel) <= 0.004) { S.vel = 0; S.snapTo = nearestFrameAngle(S.angle); }
      } else if (S.snapTo !== null && !drag.active) {
        const diff = mod(S.snapTo - S.angle + 180) - 180;
        if (Math.abs(diff) < 0.3) { S.angle = mod(S.snapTo); S.snapTo = null; updateHash(); }
        else S.angle = mod(S.angle + diff * Math.min(1, dt / 90));
      }
      render();
    }
    requestAnimationFrame(tick);
  }
  function stopAuto() { if (S.auto) toggleAuto(false); }
  function toggleAuto(on = !S.auto) {
    S.auto = on; $('autoBtn').setAttribute('aria-pressed', on);
    if (on) { resetZoom(); S.vel = 0; S.snapTo = null; } else S.snapTo = nearestFrameAngle(S.angle);
  }

  /* ---------- zoom / pan ---------- */
  function applyZoom() {
    const W = viewer.clientWidth, H = viewer.clientHeight;
    S.zoom = Math.min(MAX_ZOOM, Math.max(1, S.zoom));
    S.tx = Math.min(0, Math.max(W - W * S.zoom, S.tx));
    S.ty = Math.min(0, Math.max(H - H * S.zoom, S.ty));
    if (S.zoom <= 1.001) { S.zoom = 1; S.tx = 0; S.ty = 0; }
    stage.style.transform = `translate(${S.tx}px,${S.ty}px) scale(${S.zoom})`;
    const z = S.zoom > 1;
    viewer.classList.toggle('zoomed', z);
    $('zoomBadge').hidden = !z; $('zoomVal').textContent = S.zoom.toFixed(1) + '×';
    if (z) { stopAuto(); S.vel = 0; if (S.zoom > HI_AT) loadHi(); }
    $('hires').hidden = !(S.zoom > HI_AT && S.frames.some(f => S.hiLoaded.has(f.hi) && imgA.getAttribute('src') === f.hi));
  }
  function zoomAt(ns, px, py) {
    const s = S.zoom; ns = Math.min(MAX_ZOOM, Math.max(1, ns));
    S.tx = px - (px - S.tx) * (ns / s); S.ty = py - (py - S.ty) * (ns / s); S.zoom = ns; applyZoom();
  }
  function resetZoom(instant) {
    S.zoom = 1; S.tx = 0; S.ty = 0;
    stage.style.transition = instant ? 'none' : 'transform .28s ease';
    applyZoom(); setTimeout(() => stage.style.transition = '', 300);
    lastKey = '';
  }
  function loadHi() {
    const { p, q, t, gap } = bracket(S.angle);
    const f = gap <= BLEND_GAP ? (t < 0.5 ? p : q) : (t < 0.5 ? p : q);
    if (S.hiLoaded.has(f.hi)) { lastKey = ''; return; }
    if (f._loading) return; f._loading = true;
    const i = new Image(); i.onload = () => { S.hiLoaded.add(f.hi); f._loading = false; lastKey = ''; render(true); applyZoom(); };
    i.onerror = () => { f._loading = false; }; i.src = f.hi;
  }

  /* ---------- pointer input ---------- */
  const pts = new Map();
  const drag = { active: false, x: 0, y: 0, hist: [], pinch: null, moved: 0 };
  let lastTap = { t: 0, x: 0, y: 0 };
  const local = (e) => { const r = viewer.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const degPerPx = () => 360 / Math.max(320, viewer.clientWidth * 1.15);

  viewer.addEventListener('pointerdown', (e) => {
    viewer.focus({ preventScroll: true }); try { viewer.setPointerCapture(e.pointerId); } catch (_) {}
    pts.set(e.pointerId, local(e)); hideHint();
    if (pts.size === 1) {
      const p = local(e); Object.assign(drag, { active: true, x: p.x, y: p.y, hist: [{ x: p.x, t: e.timeStamp }], moved: 0, pinch: null });
      S.vel = 0; S.snapTo = null; stopAuto(); viewer.classList.add('dragging');
    } else if (pts.size === 2) {
      const [a, b] = [...pts.values()];
      drag.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), z: S.zoom, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2, tx: S.tx, ty: S.ty };
      drag.moved = 99;
    }
  });
  viewer.addEventListener('pointermove', (e) => {
    if (!pts.has(e.pointerId)) return;
    const p = local(e); pts.set(e.pointerId, p);
    if (drag.pinch && pts.size >= 2) {
      const [a, b] = [...pts.values()], P = drag.pinch;
      const d = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      const ns = Math.min(MAX_ZOOM, Math.max(1, P.z * d / P.d));
      S.zoom = ns;
      S.tx = mx - (P.mx - P.tx) * (ns / P.z); S.ty = my - (P.my - P.ty) * (ns / P.z);
      applyZoom(); return;
    }
    if (!drag.active) return;
    const dx = p.x - drag.x, dy = p.y - drag.y; drag.x = p.x; drag.y = p.y;
    drag.moved += Math.abs(dx) + Math.abs(dy);
    if (S.zoom > 1) { S.tx += dx; S.ty += dy; applyZoom(); return; }   // rotation locked while zoomed
    S.angle = mod(S.angle - dx * degPerPx());
    drag.hist.push({ x: p.x, t: e.timeStamp }); if (drag.hist.length > 6) drag.hist.shift();
  });
  const end = (e) => {
    if (!pts.has(e.pointerId)) return;
    pts.delete(e.pointerId);
    if (pts.size === 1 && drag.pinch) { const [p] = [...pts.values()]; drag.pinch = null; drag.x = p.x; drag.y = p.y; drag.hist = []; return; }
    if (pts.size) return;
    viewer.classList.remove('dragging');
    const wasPinch = !!drag.pinch; drag.active = false; drag.pinch = null;
    if (wasPinch) return;
    if (S.zoom === 1) {
      const h = drag.hist, a = h[0], b = h[h.length - 1];
      if (h.length > 1 && e.timeStamp - b.t < 80 && b.t > a.t) S.vel = Math.max(-1.2, Math.min(1.2, -(b.x - a.x) / (b.t - a.t) * degPerPx()));
      if (Math.abs(S.vel) <= 0.004) S.snapTo = nearestFrameAngle(S.angle);
    }
    if (drag.moved < 10) {   // tap → double-tap zoom
      const p = local(e), now = e.timeStamp;
      if (now - lastTap.t < 320 && Math.hypot(p.x - lastTap.x, p.y - lastTap.y) < 30) {
        if (S.zoom > 1) resetZoom(); else { stage.style.transition = 'transform .25s ease'; zoomAt(DBL_ZOOM, p.x, p.y); setTimeout(() => stage.style.transition = '', 260); }
        lastTap.t = 0;
      } else lastTap = { t: now, x: p.x, y: p.y };
    }
    updateHash();
  };
  viewer.addEventListener('pointerup', end);
  viewer.addEventListener('pointercancel', end);
  viewer.addEventListener('wheel', (e) => {
    e.preventDefault(); hideHint();
    const p = local(e), k = e.ctrlKey ? 0.01 : 0.0018;
    zoomAt(S.zoom * Math.exp(-e.deltaY * k), p.x, p.y);
  }, { passive: false });
  viewer.addEventListener('dblclick', (e) => e.preventDefault());
  ['gesturestart', 'gesturechange'].forEach(t => viewer.addEventListener(t, (e) => e.preventDefault()));

  /* ---------- keyboard & buttons ---------- */
  function step(dir) {
    stopAuto(); if (S.zoom > 1) resetZoom();
    const F = S.frames, cur = nearestFrameAngle(S.snapTo ?? S.angle);
    const next = F[mod(F.findIndex(f => f.angle === cur) + dir, F.length)].angle;
    let delta = mod(next - cur); if (dir < 0) delta -= 360; if (delta === 0 || delta === -360) delta = dir * 360 / Math.max(1, F.length);
    S.angle = cur; goTo(cur + delta);
  }
  document.addEventListener('keydown', (e) => {
    if (e.target.closest && e.target.closest('input,textarea')) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); step(1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
    else if (e.key === ' ' && document.activeElement === viewer) { e.preventDefault(); toggleAuto(); }
    else if (e.key === 'Escape' || e.key === '0') resetZoom();
    else if (e.key === '+' || e.key === '=') zoomAt(S.zoom * 1.4, viewer.clientWidth / 2, viewer.clientHeight / 2);
    else if (e.key === '-') zoomAt(S.zoom / 1.4, viewer.clientWidth / 2, viewer.clientHeight / 2);
  });
  $('prevBtn').addEventListener('click', () => step(-1));
  $('nextBtn').addEventListener('click', () => step(1));
  $('autoBtn').addEventListener('click', () => toggleAuto());
  $('zoomReset').addEventListener('click', (e) => { e.stopPropagation(); resetZoom(); });
  $('zoomReset').addEventListener('pointerdown', (e) => e.stopPropagation());
  window.addEventListener('resize', () => applyZoom());

  let hintTimer = setTimeout(hideHint, 6000);
  function hideHint() { $('hint').classList.add('gone'); clearTimeout(hintTimer); }
  function updateHash() {
    if (!S.model) return;
    history.replaceState(null, '', `#${S.model.id}/${S.outfit.id}/${Math.round(mod(S.snapTo ?? S.angle))}`);
  }
  window.atelier = S;  // exposed for testing
  init();
})();
