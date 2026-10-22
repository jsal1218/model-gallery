// Shared with Avata's js/outfit-drag.js (same code, ES module there).
(() => {
// Drag to reorder the outfit cards (2026-10-22, Jordan). iPhone: press and hold a card ~350 ms until it lifts, then drag it;
// a line shows where it will land; let go to drop. A quick tap still just selects the outfit; moving more than 8 px before
// the hold completes is a swipe, so the press is dropped and the page/row scrolls as normal. The order is kept per model on
// this device; outfits added later go at the end, removed ones drop out (orderOutfits). Base can move, but opening a model
// still shows Base (callers select their first manifest outfit, not the first card).
const HOLD_MS = 350, SLOP = 8, EDGE = 64;

// saved = ids in the user's order. Unknown/duplicate ids are dropped; outfits not in it keep their shipped order, after it.
function orderOutfits(outfits, saved) {
  if (!Array.isArray(saved) || !saved.length) return outfits.slice();
  const by = new Map(outfits.map(o => [o.id, o])), seen = new Set(), out = [];
  for (const id of saved) if (by.has(id) && !seen.has(id)) { seen.add(id); out.push(by.get(id)); }
  return out.concat(outfits.filter(o => !seen.has(o.id)));
}
// names for her outfits (shipped order): a given name is kept; one shipped without a name becomes "Outfit N" with the next
// number after her highest "Outfit N" (the first outfit, her Base, is "Base").
function outfitNames(outfits) {
  const named = o => o.name && String(o.name).trim();
  let n = Math.max(0, ...outfits.map(o => +((named(o) || '').match(/^Outfit (\d+)$/) || [])[1] || 0));
  return new Map(outfits.map((o, i) => [o.id, named(o) || (i ? `Outfit ${++n}` : 'Base')]));
}

function sortableCards(grid, sel, onDrop) {
  if (grid.dataset.sortable) return; grid.dataset.sortable = '1';
  let press = null, drag = null, eat = false, raf = 0;
  const mark = document.createElement('i'); mark.className = 'of-drop'; mark.setAttribute('aria-hidden', 'true');
  const cards = () => [...grid.querySelectorAll(sel)];
  const unpress = () => { if (press) { clearTimeout(press.t); press = null; } };
  grid.addEventListener('pointerdown', e => {
    if (drag || !e.isPrimary || (e.pointerType === 'mouse' && e.button !== 0)) return;
    const card = e.target.closest(sel); if (!card || !grid.contains(card)) return;
    unpress(); press = { card, id: e.pointerId, x: e.clientX, y: e.clientY };
    press.t = setTimeout(lift, HOLD_MS);
  });
  function lift() {
    if (!press || !press.card.isConnected) return unpress();
    const { card, id, x, y } = press; press = null;
    drag = { card, id, x0: x, y0: y, x, y, sy: scrollY, slot: null };
    try { card.setPointerCapture(id); } catch {}
    card.classList.add('lifted'); grid.classList.add('sorting'); grid.appendChild(mark);
    place(); tick();
  }
  function place() {
    const { card, x, y } = drag;
    card.style.transform = `translate(${x - drag.x0}px,${y - drag.y0 + scrollY - drag.sy}px) scale(1.08)`;
    let best = null, bd = Infinity;
    for (const c of cards()) {
      if (c === card) continue;
      const r = c.getBoundingClientRect(), d = Math.hypot(x - (r.left + r.width / 2), y - (r.top + r.height / 2));
      if (d < bd) { bd = d; best = { c, r }; }
    }
    if (!best) { drag.slot = null; mark.hidden = true; return; }
    const before = x < best.r.left + best.r.width / 2, gr = grid.getBoundingClientRect(), gap = parseFloat(getComputedStyle(grid).columnGap) || 6;
    drag.slot = { c: best.c, before }; mark.hidden = false;
    mark.style.left = ((before ? best.r.left - gap / 2 : best.r.right + gap / 2) - gr.left - 1.5) + 'px';
    mark.style.top = (best.r.top - gr.top) + 'px'; mark.style.height = best.r.height + 'px';
  }
  function tick() {   // near the top/bottom of the screen, scroll so a long gallery can be crossed
    cancelAnimationFrame(raf); if (!drag) return;
    const v = drag.y < EDGE ? -(EDGE - drag.y) / 5 : drag.y > innerHeight - EDGE ? (drag.y - innerHeight + EDGE) / 5 : 0;
    if (v) { scrollBy(0, v); place(); }
    raf = requestAnimationFrame(tick);
  }
  function end(drop) {
    cancelAnimationFrame(raf);
    const { card, slot } = drag; drag = null;
    card.classList.remove('lifted'); card.style.transform = ''; grid.classList.remove('sorting'); mark.remove();
    eat = true; setTimeout(() => { eat = false; }, 400);   // the release must not also count as a tap on the card
    if (!drop || !slot) return;
    const before = cards().map(c => c.dataset.id).join();
    grid.insertBefore(card, slot.before ? slot.c : slot.c.nextSibling);
    const ids = cards().map(c => c.dataset.id);
    if (ids.join() !== before) onDrop(ids);
  }
  grid.addEventListener('pointermove', e => {
    if (press && e.pointerId === press.id && Math.hypot(e.clientX - press.x, e.clientY - press.y) > SLOP) unpress();
    if (drag && e.pointerId === drag.id) { drag.x = e.clientX; drag.y = e.clientY; place(); }
  });
  grid.addEventListener('pointerup', e => { if (press && e.pointerId === press.id) unpress(); if (drag && e.pointerId === drag.id) end(true); });
  grid.addEventListener('pointercancel', e => { if (press && e.pointerId === press.id) unpress(); if (drag && e.pointerId === drag.id) end(false); });
  addEventListener('scroll', () => { if (press) unpress(); }, { passive: true });   // the page started scrolling: it's a swipe
  grid.addEventListener('touchmove', e => { if (drag && e.cancelable) e.preventDefault(); }, { passive: false }); // hold the page still while dragging
  grid.addEventListener('contextmenu', e => { if (press || drag) e.preventDefault(); });
  grid.addEventListener('dragstart', e => e.preventDefault());
  grid.addEventListener('click', e => { if (eat) { eat = false; e.stopPropagation(); e.preventDefault(); } }, true);
}
window.OutfitDrag = { orderOutfits, outfitNames, sortableCards };
})();
