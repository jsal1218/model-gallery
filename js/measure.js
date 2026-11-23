// Measurement profiles for Avata (model gallery). On-device body + garment
// measures for avatars and tech packs. Plain JS, no build step.
// Storage key and JSON format match the /avata/ copy so a file exported from
// one can be imported into the other (they share an origin).
(function () {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  const ico = (d, size = 18) =>
    `<svg class="ms-i" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  const I = {
    back: ico('<path d="M15 5l-7 7 7 7"/>'),
    down: ico('<path d="M12 4v12M7 11l5 5 5-5"/>'),
    up:   ico('<path d="M12 20V8M7 13l5-5 5 5"/>'),
    plus: ico('<path d="M12 5v14M5 12h14"/>'),
    tape: ico('<g fill="none"><rect x="3" y="8.5" width="13" height="9" rx="2"/><path d="M16 11.5h5v5h-5"/><path d="M6.5 11.5v3M9 11.5v3M11.5 11.5v3"/></g>', 22),
  };

  function toast(msg) {
    let host = $('#msToasts');
    if (!host) {
      host = document.createElement('div');
      host.id = 'msToasts';
      document.body.append(host);
    }
    const t = document.createElement('div');
    t.className = 'ms-toast';
    t.setAttribute('role', 'status');
    t.textContent = msg;
    host.append(t);
    setTimeout(() => t.remove(), 3600);
  }

  async function shareOrDownload(blob, name, title) {
    const file = new File([blob], name, { type: blob.type || 'application/json' });
    if (navigator.canShare?.({ files: [file] })) {
      try { await navigator.share({ files: [file], title }); return 'shared'; }
      catch (e) { if (e.name === 'AbortError') return 'aborted'; }
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    return 'downloaded';
  }

const STORAGE_KEY = 'avata-measure-profiles';
const FORMAT = 1;
const TEST_PROFILE_ID = 'test-male-5ft6-130';
const TEST_PROFILE_URL = 'data/profiles/test-male-5ft6-130.json';
const DEFAULTS_URL = 'data/profiles/jordan-default.json';

/** Body points of measure, US units. `kind` is 'ftin' | 'lb' | 'in'. */
const MEASURES = [
  { id: 'height', kind: 'ftin', label: 'Height', view: 'front',
    how: 'Stand barefoot against a wall, feet together, looking straight ahead. Have a helper mark the top of your head and measure from the floor to that mark, in feet and inches.' },
  { id: 'weight', kind: 'lb', label: 'Weight', view: 'front',
    how: 'Weigh yourself in the morning, after using the bathroom, in fitted underwear or a thin base layer. Use the same scale each time and record pounds.' },
  { id: 'neck', kind: 'in', label: 'Neck', view: 'front',
    how: 'Wrap the tape around the base of your neck, where a shirt collar sits. Keep it level and snug — you should be able to slip one finger under the tape.' },
  { id: 'shoulder', kind: 'in', label: 'Shoulder width', view: 'back',
    how: 'With arms relaxed, measure a straight line across the back from the bony tip of one shoulder (the acromion) to the other. Do not follow the curve of the back.' },
  { id: 'chest', kind: 'in', label: 'Chest', view: 'front',
    how: 'Wrap the tape around the fullest part of the chest, under the arms and across the shoulder blades, keeping it level all the way around. Breathe normally; the tape should be snug but not tight.' },
  { id: 'waist', kind: 'in', label: 'Waist', view: 'front',
    how: 'Find the natural waist — usually the narrowest point, just above the navel, where you bend to the side. Keep the tape level and snug. Stand relaxed; do not suck in.' },
  { id: 'highHip', kind: 'in', label: 'High hip', view: 'front',
    how: 'Measure about 3 to 4 inches below the natural waist, where the hip begins to widen. Keep the tape level and snug, not tight.' },
  { id: 'hip', kind: 'in', label: 'Hip / seat', view: 'front',
    how: 'Wrap the tape around the fullest part of the seat, usually 7 to 9 inches below the waist. Keep it level all the way around and include both sides of the seat.' },
  { id: 'sleeve', kind: 'in', label: 'Sleeve length', view: 'front',
    how: 'From the bony tip of the shoulder (acromion) down the outside of the arm, over a slightly bent elbow, to the wrist bone. This is the usual sleeve length.' },
  { id: 'arm', kind: 'in', label: 'Arm length', view: 'back',
    how: 'From the nape (center back of the neck) over the shoulder and down the arm, over a slightly bent elbow, to the wrist bone. This is longer than sleeve length.' },
  { id: 'bicep', kind: 'in', label: 'Bicep', view: 'front',
    how: 'Wrap the tape around the fullest part of the upper arm, with the arm hanging relaxed at your side. Keep it snug, and do not flex.' },
  { id: 'wrist', kind: 'in', label: 'Wrist', view: 'front',
    how: 'Wrap the tape around the wrist just over the wrist bone, where a cuff would sit. Snug enough to stay put, loose enough to slip a finger under.' },
  { id: 'torso', kind: 'in', label: 'Torso length', view: 'front',
    how: 'From the high point of the shoulder (HPS — where a shoulder seam would sit, next to the neck) straight down the front to the natural waist.' },
  { id: 'back', kind: 'in', label: 'Back length', view: 'back',
    how: 'From the nape (the prominent bone at the center back of the neck) straight down the spine to the natural waist.' },
  { id: 'frontRise', kind: 'in', label: 'Front rise', view: 'front',
    how: 'From the natural waist at center front, down to the crotch point (where the inside-leg seams of a pair of pants would meet). Keep the tape close to the body.' },
  { id: 'backRise', kind: 'in', label: 'Back rise', view: 'back',
    how: 'From the natural waist at center back, down over the seat to the same crotch point. This should be longer than the front rise.' },
  { id: 'inseam', kind: 'in', label: 'Inseam', view: 'front',
    how: 'From the crotch point down the inside of the leg to the floor, or to where you want the hem. Stand straight and barefoot unless you always wear a set heel.' },
  { id: 'outseam', kind: 'in', label: 'Outseam', view: 'side',
    how: 'From the natural waist at the side, straight down over the hip to the floor, or to the same hem as the inseam.' },
  { id: 'thigh', kind: 'in', label: 'Thigh', view: 'front',
    how: 'Wrap the tape around the fullest part of the upper thigh, usually 1 to 2 inches below the crotch. Keep it level and snug, not tight.' },
  { id: 'knee', kind: 'in', label: 'Knee', view: 'front',
    how: 'Wrap the tape around the knee at the kneecap, with the leg straight and relaxed. Keep the tape level.' },
  { id: 'calf', kind: 'in', label: 'Calf', view: 'front',
    how: 'Wrap the tape around the fullest part of the calf, usually a few inches below the knee. Keep it level and snug.' },
  { id: 'ankle', kind: 'in', label: 'Ankle', view: 'front',
    how: 'Wrap the tape around the ankle just above the ankle bone, where a pant hem would typically sit. Keep it snug, not tight.' },
];

const GARMENT_FIELDS = [
  { id: 'type', kind: 'text', label: 'Garment type', placeholder: 'e.g. favorite jeans, fitted tee' },
  { id: 'chestWidth', kind: 'in', label: 'Chest width', how: 'Laid flat, measure straight across the chest, from side fold to side fold, at the underarm. This is half the circumference — do not wrap around.' },
  { id: 'waistWidth', kind: 'in', label: 'Waist width', how: 'Laid flat, measure straight across at the waist or waistband, from fold to fold, unstretched.' },
  { id: 'length', kind: 'in', label: 'Length', how: 'For a top, high point of the shoulder down to the hem. For pants, the side waist down to the hem (outseam), or the center-back waist to the hem if that is how you usually measure that garment.' },
  { id: 'sleeve', kind: 'in', label: 'Sleeve', how: 'Laid flat, from the shoulder point (or the collar join on a raglan) to the end of the cuff, along the outside edge.' },
  { id: 'inseam', kind: 'in', label: 'Inseam', how: 'Laid flat, from the crotch join down the inside leg to the hem. Use this for pants and shorts; leave it blank on a top.' },
];

// Gentle ranges. Empty is always fine. Values outside get a warning, not a block.
const RANGES = {
  height: [48, 90],        // 4 ft – 7 ft 6 in, total inches
  weight: [70, 400],
  neck: [10, 22],
  shoulder: [12, 26],
  chest: [26, 62],
  waist: [20, 62],
  highHip: [24, 64],
  hip: [28, 72],
  sleeve: [18, 40],
  arm: [24, 42],
  bicep: [7, 22],
  wrist: [5, 10],
  torso: [12, 22],
  back: [13, 22],
  frontRise: [6, 18],
  backRise: [9, 22],
  inseam: [22, 38],
  outseam: [28, 50],
  thigh: [14, 36],
  knee: [10, 24],
  calf: [10, 24],
  ankle: [7, 14],
  chestWidth: [10, 30],
  waistWidth: [8, 30],
  length: [8, 50],
  gSleeve: [4, 28],
  gInseam: [2, 38],
};

function warnValue(id, raw, kind = 'in') {
  if (raw === '' || raw == null) return '';
  const n = Number(raw);
  if (!Number.isFinite(n)) return 'Enter a number.';
  if (n <= 0) return 'That value looks too small. Check the tape.';
  const range = RANGES[id];
  if (!range) return '';
  const [lo, hi] = range;
  const unit = kind === 'lb' ? 'lb' : 'in';
  if (n < lo) return `That looks low for this measurement (typical is about ${lo}–${hi} ${unit}). Check the tape — you can still keep it.`;
  if (n > hi) return `That looks high for this measurement (typical is about ${lo}–${hi} ${unit}). Check the tape — you can still keep it.`;
  return '';
}

function splitHeight(totalIn) {
  if (totalIn == null || totalIn === '') return { ft: '', inch: '' };
  const t = Number(totalIn);
  if (!Number.isFinite(t) || t <= 0) return { ft: '', inch: '' };
  let ft = Math.floor(t / 12), inch = Math.round((t - ft * 12) * 8) / 8;
  if (inch === 12) { ft += 1; inch = 0; }
  return { ft, inch };
}
function joinHeight(ft, inch) {
  const f = Number(ft), i = Number(inch || 0);
  if (!Number.isFinite(f) || f < 0) return '';
  if (!ft && ft !== 0 && (inch === '' || inch == null)) return '';
  if (ft === '' && (inch === '' || inch == null)) return '';
  const t = (Number.isFinite(f) ? f : 0) * 12 + (Number.isFinite(i) ? i : 0);
  return t > 0 ? t : '';
}

function uid() { return 'p-' + Math.random().toString(36).slice(2, 9) + Date.now().toString(36); }

function emptyProfile(name = 'Jordan') {
  return { id: uid(), name, values: {}, garments: [], updatedAt: Date.now() };
}

function defaultState() {
  const p = emptyProfile('Jordan');
  p.id = 'jordan';
  return { format: FORMAT, activeId: p.id, profiles: [p] };
}

function memStore() {
  const m = new Map();
  return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k) };
}

function loadState(storage) {
  const s = storage || (typeof localStorage === 'undefined' ? memStore() : localStorage);
  try {
    const raw = s.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const data = JSON.parse(raw);
    return normalizeState(data);
  } catch {
    return defaultState();
  }
}

function normalizeState(data) {
  if (!data || typeof data !== 'object') return defaultState();
  let profiles = Array.isArray(data.profiles) ? data.profiles : (data.name || data.values ? [data] : []);
  profiles = profiles.map(p => {
    const out = {
      id: String(p.id || uid()),
      name: String(p.name || '').trim() || 'Jordan',
      values: p.values && typeof p.values === 'object' ? { ...p.values } : {},
      garments: Array.isArray(p.garments) ? p.garments.slice(0, 3).map(g => ({ ...g })) : [],
      updatedAt: Number(p.updatedAt) || Date.now(),
    };
    if (p.modelId) out.modelId = String(p.modelId);
    if (Array.isArray(p.given)) out.given = p.given.map(String);
    if (Array.isArray(p.estimated)) out.estimated = p.estimated.map(String);
    if (Array.isArray(p.defaults)) out.defaults = p.defaults.map(String);
    if (p.notes) out.notes = String(p.notes);
    return out;
  }).filter(Boolean);
  if (!profiles.length) return defaultState();
  const activeId = profiles.some(p => p.id === data.activeId) ? data.activeId : profiles[0].id;
  return { format: FORMAT, activeId, profiles };
}

function saveState(state, storage) {
  const s = storage || (typeof localStorage === 'undefined' ? memStore() : localStorage);
  const clean = normalizeState(state);
  s.setItem(STORAGE_KEY, JSON.stringify(clean));
  return clean;
}

function toExportJson(state) {
  const clean = normalizeState(state);
  return JSON.stringify({
    app: 'avata-measure',
    format: FORMAT,
    exportedAt: new Date().toISOString(),
    activeId: clean.activeId,
    profiles: clean.profiles,
  }, null, 2);
}

function fromImportJson(text) {
  const data = JSON.parse(text);
  if (data.app && data.app !== 'avata-measure' && data.app !== 'avata') {
    // still try if it looks like a profile file
    if (!data.profiles && !data.values && !data.name) throw new Error('This file is not a measurement profile.');
  }
  const st = normalizeState(data);
  if (!st.profiles.length) throw new Error('This file has no profiles in it.');
  return st;
}

function activeProfile(state) {
  // Return the live profile object so edits persist (do not clone).
  if (!state || !Array.isArray(state.profiles) || !state.profiles.length) {
    const d = defaultState();
    if (state && typeof state === 'object') {
      state.format = d.format; state.activeId = d.activeId; state.profiles = d.profiles;
      return state.profiles[0];
    }
    return d.profiles[0];
  }
  const p = state.profiles.find(x => x.id === state.activeId) || state.profiles[0];
  if (!p.values || typeof p.values !== 'object') p.values = {};
  if (!Array.isArray(p.garments)) p.garments = [];
  return p;
}

function profileSummary(state) {
  const p = activeProfile(state);
  const filled = MEASURES.filter(m => {
    const v = p.values[m.id];
    return v !== '' && v != null && Number(v) > 0;
  }).length;
  const g = (p.garments || []).filter(x => x && (x.type || x.chestWidth || x.waistWidth || x.length || x.sleeve || x.inseam)).length;
  return { name: p.name || 'Jordan', filled, total: MEASURES.length, garments: g };
}

// ---------- diagrams (original line drawings) ----------
const FRONT = `
  <g class="ms-body">
    <circle cx="80" cy="30" r="13"/>
    <path d="M73 43 v7 h14 v-7"/>
    <path d="M73 50 L50 56 L40 102 L36 152"/>
    <path d="M36 152l-3 8m3-8l5 7"/>
    <path d="M87 50 L110 56 L120 102 L124 152"/>
    <path d="M124 152l-5 7m5-7l3 8"/>
    <path d="M62 70 L66 118 C67 132 63 148 64 156 C64 164 70 170 80 170 C90 170 96 164 96 156 C97 148 93 132 94 118 L98 70"/>
    <path d="M70 170 C68 192 65 214 64 228 C64 250 66 270 68 288 L62 306 L78 306 L74 288 C74 270 76 250 76 228 C77 214 78 192 80 170"/>
    <path d="M90 170 C92 192 95 214 96 228 C96 250 94 270 92 288 L98 306 L82 306 L86 288 C86 270 84 250 84 228 C83 214 82 192 80 170"/>
  </g>`;

const BACK = `
  <g class="ms-body">
    <circle cx="80" cy="30" r="13"/>
    <path d="M73 43 v7 h14 v-7"/>
    <path d="M80 43 v5"/>
    <path d="M73 50 L50 56 L40 102 L36 152"/>
    <path d="M36 152l-3 8m3-8l5 7"/>
    <path d="M87 50 L110 56 L120 102 L124 152"/>
    <path d="M124 152l-5 7m5-7l3 8"/>
    <path d="M62 70 L66 118 C67 132 63 148 64 156 C64 164 70 170 80 170 C90 170 96 164 96 156 C97 148 93 132 94 118 L98 70"/>
    <path d="M70 170 C68 192 65 214 64 228 C64 250 66 270 68 288 L62 306 L78 306 L74 288 C74 270 76 250 76 228 C77 214 78 192 80 170"/>
    <path d="M90 170 C92 192 95 214 96 228 C96 250 94 270 92 288 L98 306 L82 306 L86 288 C86 270 84 250 84 228 C83 214 82 192 80 170"/>
  </g>`;

const SIDE = `
  <g class="ms-body">
    <ellipse cx="86" cy="30" rx="12" ry="13"/>
    <path d="M80 43 v8"/>
    <path d="M80 51 C72 58 70 80 72 118 C73 140 68 155 70 168 C68 200 70 230 72 258 C74 278 76 288 78 304 L96 304 C94 288 92 270 92 250 C94 220 96 190 94 168 C100 155 104 140 102 118 C104 80 100 58 92 51"/>
    <path d="M90 58 L96 100 L98 150"/>
    <path d="M98 150l2 8"/>
  </g>`;

function wrap(inner, label, h = 320) {
  return `<svg class="ms-svg" viewBox="0 0 160 ${h}" role="img" aria-label="${esc(label)}" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}
function cap(x, y, t, anchor = 'middle') {
  const cls = anchor === 'middle' ? 'ms-cap' : `ms-cap ${anchor}`;
  return `<text class="${cls}" x="${x}" y="${y}">${t}</text>`;
}

function arrowHead(x, y, ang, s = 6) {
  const x1 = x - s * Math.cos(ang - 0.45), y1 = y - s * Math.sin(ang - 0.45);
  const x2 = x - s * Math.cos(ang + 0.45), y2 = y - s * Math.sin(ang + 0.45);
  return `M${x} ${y}L${x1.toFixed(1)} ${y1.toFixed(1)}M${x} ${y}L${x2.toFixed(1)} ${y2.toFixed(1)}`;
}
function vArrow(x, y1, y2) {
  const dir = y2 >= y1 ? 1 : -1;
  return `<path class="ms-tape" d="M${x} ${y1}V${y2}"/>
    <path class="ms-arrow" d="${arrowHead(x, y1, dir < 0 ? Math.PI / 2 : -Math.PI / 2)}${arrowHead(x, y2, dir > 0 ? Math.PI / 2 : -Math.PI / 2)}"/>`;
}
function hArrow(x1, x2, y) {
  return `<path class="ms-tape" d="M${x1} ${y}H${x2}"/>
    <path class="ms-arrow" d="${arrowHead(x1, y, Math.PI)}${arrowHead(x2, y, 0)}"/>`;
}
function around(cx, cy, rx, ry = 7) {
  return `<ellipse class="ms-tape" cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}"/>
    <path class="ms-arrow" d="${arrowHead(cx + rx, cy, 0.3)}"/>`;
}
function pathArrow(d, hx, hy, ang) {
  return `<path class="ms-tape" d="${d}"/>
    <path class="ms-arrow" d="${arrowHead(hx, hy, ang)}"/>`;
}

const DIAG = {
  height: () => wrap(FRONT + vArrow(18, 17, 306) + cap(6, 164, 'floor to', 'start') + cap(6, 176, 'crown', 'start'), 'Height: floor to the top of the head, front view'),
  weight: () => wrap(FRONT + `
    <rect class="ms-tape" x="48" y="306" width="64" height="8" rx="1.5" fill="none"/>
    <path class="ms-tape" d="M40 314 H120"/>
    ` + cap(124, 318, 'scale', 'start'), 'Weight: stand on a scale in light clothing', 332),
  neck: () => wrap(FRONT + around(80, 47, 12, 5) + cap(108, 52, 'base of neck', 'start'), 'Neck: tape around the base of the neck'),
  shoulder: () => wrap(BACK + hArrow(50, 110, 54) + cap(116, 50, 'acromion', 'start') + cap(116, 62, 'to acromion', 'start'), 'Shoulder width: straight across the back, bone to bone'),
  chest: () => wrap(FRONT + around(80, 80, 32, 9) + cap(116, 74, 'fullest part,', 'start') + cap(116, 86, 'under arms', 'start'), 'Chest: tape around the fullest part of the chest'),
  waist: () => wrap(FRONT + around(80, 118, 22, 7) + cap(116, 122, 'natural waist', 'start'), 'Waist: tape around the natural waist'),
  highHip: () => wrap(FRONT + around(80, 136, 26, 7) + cap(116, 140, '3–4 in below waist', 'start'), 'High hip: tape about 3 to 4 inches below the waist'),
  hip: () => wrap(FRONT + around(80, 154, 30, 8) + cap(116, 158, 'fullest of the seat', 'start'), 'Hip and seat: tape around the fullest part'),
  sleeve: () => wrap(FRONT + pathArrow('M110 56 L120 102 L124 152', 124, 152, 1.3) + cap(128, 100, 'shoulder to wrist', 'start'), 'Sleeve length: shoulder tip down the arm to the wrist'),
  arm: () => wrap(BACK + pathArrow('M80 46 L110 56 L120 102 L124 152', 124, 152, 1.3) + cap(116, 36, 'CB neck to wrist', 'start'), 'Arm length: center-back neck, over the shoulder, to the wrist'),
  bicep: () => wrap(FRONT + around(42, 100, 10, 6) + cap(28, 86, 'fullest, relaxed', 'end'), 'Bicep: tape around the upper arm, relaxed'),
  wrist: () => wrap(FRONT + around(36, 152, 7, 5) + cap(28, 172, 'at the wrist bone', 'end'), 'Wrist: tape around the wrist bone'),
  torso: () => wrap(FRONT + vArrow(70, 50, 118) + cap(8, 90, 'HPS to waist', 'start'), 'Torso length: high-point shoulder down the front to the waist'),
  back: () => wrap(BACK + vArrow(80, 46, 118) + cap(96, 90, 'CB neck to waist', 'start'), 'Back length: nape straight down the spine to the waist'),
  frontRise: () => wrap(FRONT + pathArrow('M80 118 L80 170', 80, 170, Math.PI / 2) + cap(96, 148, 'CF waist to crotch', 'start'), 'Front rise: center-front waist down to the crotch'),
  backRise: () => wrap(BACK + pathArrow('M80 118 C96 140 94 158 80 170', 80, 170, 2.2) + cap(110, 150, 'CB waist over the seat', 'start'), 'Back rise: center-back waist over the seat to the crotch'),
  inseam: () => wrap(FRONT + vArrow(80, 170, 306) + cap(96, 240, 'crotch to floor', 'start'), 'Inseam: crotch down the inside of the leg to the floor or hem'),
  outseam: () => wrap(SIDE + vArrow(48, 118, 304) + cap(6, 210, 'side waist', 'start') + cap(6, 222, 'to floor', 'start'), 'Outseam: side waist down to the floor or hem, side view'),
  thigh: () => wrap(FRONT + around(68, 190, 16, 8) + cap(48, 176, 'fullest thigh', 'end'), 'Thigh: tape around the fullest part of the upper thigh'),
  knee: () => wrap(FRONT + around(66, 228, 13, 7) + cap(50, 216, 'at the kneecap', 'end'), 'Knee: tape around the knee'),
  calf: () => wrap(FRONT + around(68, 258, 14, 7) + cap(50, 246, 'fullest calf', 'end'), 'Calf: tape around the fullest part of the calf'),
  ankle: () => wrap(FRONT + around(70, 290, 10, 5) + cap(56, 280, 'above the ankle bone', 'end'), 'Ankle: tape just above the ankle bone'),
};

function diagramFor(id) { return (DIAG[id] || DIAG.height)(); }

function garmentTopSvg() {
  return `<svg class="ms-svg" viewBox="0 0 200 200" role="img" aria-label="Flat top: chest width, waist width, length and sleeve" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
    <g class="ms-body">
      <path d="M70 28 L50 40 L40 70 L44 150 H156 L160 70 L150 40 L130 28 L120 48 H80 Z"/>
      <path d="M70 28 C80 38 120 38 130 28"/>
    </g>
    ${hArrow(44, 156, 78)}
    <text class="ms-cap" x="100" y="70">chest width</text>
    ${hArrow(52, 148, 132)}
    <text class="ms-cap" x="100" y="124">waist width</text>
    ${vArrow(100, 28, 150)}
    <text class="ms-cap" x="110" y="96">length</text>
    <path class="ms-tape" d="M150 40 L160 70"/>
    <path class="ms-arrow" d="${arrowHead(160, 70, 1.1)}"/>
    <text class="ms-cap" x="168" y="58">sleeve</text>
  </svg>`;
}
function garmentPantSvg() {
  return `<svg class="ms-svg" viewBox="0 0 200 220" role="img" aria-label="Flat pants: waist width, inseam and outseam" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
    <g class="ms-body">
      <path d="M60 24 H140 L150 48 L130 200 H108 L100 90 L92 200 H70 L50 48 Z"/>
      <path d="M60 24 H140 L138 40 H62 Z"/>
    </g>
    ${hArrow(60, 140, 32)}
    <text class="ms-cap" x="100" y="20">waist width</text>
    ${vArrow(100, 90, 200)}
    <text class="ms-cap" x="110" y="150">inseam</text>
    ${vArrow(44, 32, 200)}
    <text class="ms-cap" x="20" y="120">length</text>
  </svg>`;
}

const garmentDiagrams = { top: garmentTopSvg, pants: garmentPantSvg };


  // ---------- view ----------
  let state;
  let root;
  let openFlag = false;
  let onClose = null;
  let lastFocus = null;

  function persist() { state = saveState(state); }
  function fmtFilled(s) { return s.filled ? `${s.filled} of ${s.total} body measures` : 'No measurements yet'; }

  function isMeasureHash() {
    return location.hash.replace(/^#/, '').split('/')[0] === 'measure';
  }

  function measureView() {
    let el = $('#measureView');
    if (!el) {
      el = document.createElement('div');
      el.id = 'measureView';
      el.hidden = true;
      document.body.append(el);
    }
    return el;
  }

  function entryCopy() {
    const s = profileSummary(loadState());
    const sub = s.filled
      ? `${s.name} · ${s.filled} of ${s.total} filled`
      : `${s.name} · for tech packs and avatars`;
    return { name: s.name, sub };
  }

  function mountEntry(panel) {
    if (!panel) return;
    let el = $('#measureEntry');
    if (!el) {
      el = document.createElement('a');
      el.id = 'measureEntry';
      el.className = 'ms-entry';
      el.href = '#measure';
      const h2 = panel.querySelector('h2');
      panel.insertBefore(el, h2 || panel.firstChild);
      el.addEventListener('click', ev => {
        ev.preventDefault();
        open();
      });
    }
    refreshEntry();
  }

  function refreshEntry() {
    const el = $('#measureEntry');
    if (!el) return;
    const { sub } = entryCopy();
    el.innerHTML = `${I.tape}<span class="ms-entry-copy"><small>Measure</small><b>Measurement profile</b><em>${esc(sub)}</em></span><span class="pill">Open</span>`;
  }

  function renderMeasure(v) {
    state = loadState();
    const p = activeProfile(state);
    const sum = profileSummary(state);

    const profileSwitch = state.profiles.length > 1
      ? `<label class="ms-field" style="margin-top:12px"><span>Profile</span>
          <select id="msActive">${state.profiles.map(x => `<option value="${esc(x.id)}" ${x.id === p.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></label>`
      : '';

    v.innerHTML = `<div class="ms-bar">
        <button type="button" class="pill" id="msBack">${I.back}<span>Models</span></button>
      </div>
      <h1 class="ms-title">Measurement <em>profile</em></h1>
      <p class="ms-lede">Saved on this device for avatars and tech packs. US units only — inches, feet and inches, and pounds. Changes save as you type.</p>

      <section class="ms-box">
        <label class="ms-field"><span>Name</span><input type="text" id="msName" value="${esc(p.name)}" maxlength="60" autocomplete="name"></label>
        ${profileSwitch}
        <p class="ms-meta" id="msMeta">${esc(fmtFilled(sum))}${sum.garments ? ` · ${sum.garments} garment${sum.garments > 1 ? 's' : ''}` : ''}</p>
        <div class="ms-actions">
          <button type="button" class="pill" id="msExp">${I.down}<span>Export</span></button>
          <button type="button" class="pill" id="msImp">${I.up}<span>Import</span></button>
          <input type="file" id="msFile" accept=".json,application/json" hidden>
        </div>
        <p class="ms-links"><button type="button" class="ms-link" id="msNew">New profile</button> · <button type="button" class="ms-link" id="msFillDef">Fill defaults</button> · <button type="button" class="ms-link" id="msLoadTest">Load test profile</button>${state.profiles.length > 1 ? ` · <button type="button" class="ms-link" id="msDel">Delete this profile</button>` : ''}</p>
      </section>
      ${fitNote(p)}

      <div class="ms-tips"><b>Before you start.</b> Wear fitted underwear or a thin base layer. Use a soft (not rigid) tape. Get a helper for the back, shoulders and anything that wraps around. Stand relaxed, feet together, looking ahead — don’t suck in. Measure twice and use the average.</div>

      <p class="ms-kicker">Body</p>
      ${MEASURES.map(m => measureCard(m, p)).join('')}

      <p class="ms-kicker" style="margin-top:6px">Garments that fit <span>optional</span></p>
      <p class="ms-lede">Measure 1 to 3 garments that already fit you well, laid flat and unstretched. Widths are fold-to-fold (half the circumference). These help later when a tech pack or avatar needs a known fit.</p>
      <div class="ms-box ms-flat">
        <p class="ms-kicker" style="margin:0 0 8px">How to measure a garment flat</p>
        <div class="ms-gdiags">
          <figure>${garmentTopSvg()}<figcaption>Top — chest width, waist width, length, sleeve</figcaption></figure>
          <figure>${garmentPantSvg()}<figcaption>Pants — waist width, length, inseam</figcaption></figure>
        </div>
      </div>
      <div id="msGarments">${(p.garments.length ? p.garments : [{}]).map((g, i) => garmentCard(g, i)).join('')}</div>
      ${(p.garments.length || 0) < 3 ? `<button type="button" class="pill ms-block" id="msAddG">${I.plus}<span>Add another garment</span></button>` : ''}`;

    bindMeasure(v);
  }

  function sourceBadge(id, given, estimated, defaults) {
    if ((defaults || []).includes(id)) return ' <span class="ms-flag default">default</span> <span class="ms-flag est">est.</span>';
    if ((given || []).includes(id)) return ' <span class="ms-flag given">given</span>';
    if ((estimated || []).includes(id)) return ' <span class="ms-flag est">est.</span>';
    return '';
  }

  function fitNote(p) {
    const model = (p.modelId === 'exact-28' || p.id === TEST_PROFILE_ID)
      ? `<a class="ms-link" id="msFitLink" href="#exact-28/base/0">Model 6</a> (exact-28).`
      : (p.modelId ? esc(p.modelId) + '.' : '');
    if (p.id === TEST_PROFILE_ID) {
      return `<div class="ms-fit" id="msFit"><b>${esc(p.name)}</b> is a test fixture. ${model} Height 5 ft 6 in and weight 130 lb are <span class="ms-flag given">given</span>, as are the reference chino’s finished waist (31 in) and outseam (35 in). All other body measures are <span class="ms-flag est">est.</span> from slim-male proportions. Loading this profile does not change Jordan.</div>`;
    }
    if ((p.defaults || []).length) {
      return `<div class="ms-fit" id="msFit">Starting numbers for <b>${esc(p.name)}</b> match the 5 ft 6 in / 130 lb slim-male build. ${model} Every filled default is a <span class="ms-flag default">default</span> / <span class="ms-flag est">est.</span> for you to replace with a tape measure. <b>Fill defaults</b> only writes empty fields — numbers you already typed are not changed.</div>`;
    }
    return '';
  }

  function measureCard(m, profile) {
    const values = profile.values || {};
    const v = values[m.id];
    const warning = m.kind === 'ftin' ? warnValue('height', v, 'in') : warnValue(m.id, v, m.kind);
    const flag = sourceBadge(m.id, profile.given, profile.estimated, profile.defaults);
    let field;
    if (m.kind === 'ftin') {
      const { ft, inch } = splitHeight(v);
      field = `<div class="ms-split">
        <label class="ms-field"><span>Feet</span><input type="number" inputmode="numeric" min="0" max="8" step="1" data-h="ft" value="${ft}" placeholder="ft" aria-label="Height, feet"></label>
        <label class="ms-field"><span>Inches</span><input type="number" inputmode="decimal" min="0" max="11.75" step="0.25" data-h="in" value="${inch}" placeholder="in" aria-label="Height, inches"></label>
      </div>`;
    } else if (m.kind === 'lb') {
      field = `<label class="ms-field"><span>Pounds</span><input type="number" inputmode="decimal" min="0" step="0.2" data-k="${m.id}" value="${v ?? ''}" placeholder="lb" aria-label="Weight in pounds"></label>`;
    } else {
      field = `<label class="ms-field"><span>Inches</span><input type="number" inputmode="decimal" min="0" step="0.25" data-k="${m.id}" value="${v ?? ''}" placeholder="in" aria-label="${esc(m.label)} in inches"></label>`;
    }
    return `<section class="ms-box ms-card" data-measure="${m.id}" id="ms-${m.id}">
      <p class="ms-kicker">${esc(m.label)}${flag} <span>${m.view} view</span></p>
      <div class="ms-diag">${diagramFor(m.id)}</div>
      ${field}
      <p class="ms-how">${esc(m.how)}</p>
      <p class="ms-warn" ${warning ? '' : 'hidden'}>${esc(warning)}</p>
    </section>`;
  }

  function garmentCard(g = {}, i) {
    const finished = g.waistFinished ? `<p class="ms-how">Finished waist (circumference): <b>${esc(g.waistFinished)} in</b>${sourceBadge('waistFinished', g.given, g.estimated, g.defaults)}. Flat width below is half of that.</p>` : '';
    const fields = GARMENT_FIELDS.map(f => {
      if (f.kind === 'text') return `<label class="ms-field"><span>${esc(f.label)}</span><input type="text" data-g="${i}" data-gf="type" value="${esc(g.type || '')}" placeholder="${esc(f.placeholder)}"></label>${finished}`;
      const warn = warnValue(f.id === 'sleeve' ? 'gSleeve' : f.id === 'inseam' ? 'gInseam' : f.id, g[f.id], 'in');
      const flag = sourceBadge(f.id === 'length' ? 'length' : f.id, g.given, g.estimated, g.defaults);
      return `<label class="ms-field"><span>${esc(f.label)} (in)${flag}</span>
        <input type="number" inputmode="decimal" min="0" step="0.25" data-g="${i}" data-gf="${f.id}" value="${g[f.id] ?? ''}" placeholder="in" aria-label="${esc(f.label)} in inches">
        <p class="ms-how">${esc(f.how)}</p>
        <p class="ms-warn" ${warn ? '' : 'hidden'} data-gw="${i}-${f.id}">${esc(warn)}</p>
      </label>`;
    }).join('');
    return `<section class="ms-box ms-gcard" data-gi="${i}">
      <div class="ms-ghead"><p class="ms-kicker" style="margin:0">Garment ${i + 1}</p>${i > 0 ? `<button type="button" class="ms-link" data-rmg="${i}">Remove</button>` : ''}</div>
      ${fields}
    </section>`;
  }

  function bindMeasure(rootEl) {
    const p = () => activeProfile(state);
    const touch = () => { p().updatedAt = Date.now(); persist(); refreshMeta(rootEl); refreshEntry(); };

    const saveName = debounce(() => {
      const name = $('#msName', rootEl).value.trim() || 'Jordan';
      p().name = name;
      if ($('#msName', rootEl).value.trim() === '') $('#msName', rootEl).value = name;
      touch();
    }, 200);
    $('#msName', rootEl).addEventListener('input', saveName);

    $('#msBack', rootEl).onclick = () => close();

    $('#msActive', rootEl)?.addEventListener('change', e => {
      state.activeId = e.target.value;
      persist();
      renderMeasure(rootEl);
    });

    $('#msNew', rootEl).onclick = () => {
      const np = emptyProfile('Untitled');
      state.profiles.push(np);
      state.activeId = np.id;
      persist();
      renderMeasure(rootEl);
      toast('New profile started.');
    };
    $('#msLoadTest', rootEl).onclick = () => loadTestProfile(rootEl);
    $('#msFillDef', rootEl).onclick = () => fillDefaults(rootEl);
    $('#msFitLink', rootEl)?.addEventListener('click', ev => {
      ev.preventDefault();
      close({ fromHash: true });
      location.hash = 'exact-28/base/0';
    });
    $('#msDel', rootEl)?.addEventListener('click', () => {
      if (state.profiles.length < 2) return;
      if (!confirm(`Delete the profile “${p().name}”? This cannot be undone.`)) return;
      state.profiles = state.profiles.filter(x => x.id !== p().id);
      state.activeId = state.profiles[0].id;
      persist();
      renderMeasure(rootEl);
      toast('Profile deleted.');
    });

    $('#msExp', rootEl).onclick = async () => {
      const blob = new Blob([toExportJson(state)], { type: 'application/json' });
      const slug = (p().name || 'jordan').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'jordan';
      const r = await shareOrDownload(blob, `${slug}-measurements.json`, `${p().name} measurements`);
      if (r === 'downloaded') toast('Measurement file saved.');
    };
    $('#msImp', rootEl).onclick = () => $('#msFile', rootEl).click();
    $('#msFile', rootEl).onchange = async () => {
      const f = $('#msFile', rootEl).files?.[0];
      $('#msFile', rootEl).value = '';
      if (!f) return;
      try {
        const imported = fromImportJson(await f.text());
        const byId = new Map(state.profiles.map(x => [x.id, x]));
        for (const ip of imported.profiles) {
          if (byId.has(ip.id)) Object.assign(byId.get(ip.id), ip);
          else state.profiles.push(ip);
        }
        state.activeId = imported.activeId && state.profiles.some(x => x.id === imported.activeId)
          ? imported.activeId : state.activeId;
        persist();
        renderMeasure(rootEl);
        refreshEntry();
        toast('Measurements imported.');
      } catch (e) {
        toast(e.message || 'Could not read that file.');
      }
    };

    rootEl.querySelectorAll('.ms-card').forEach(card => {
      const id = card.dataset.measure;
      const setWarn = val => {
        const kind = MEASURES.find(m => m.id === id)?.kind === 'lb' ? 'lb' : 'in';
        const msg = warnValue(id === 'height' ? 'height' : id, val, kind);
        const el = card.querySelector('.ms-warn');
        el.hidden = !msg;
        el.textContent = msg;
      };
      if (id === 'height') {
        const read = () => joinHeight(card.querySelector('[data-h=ft]').value, card.querySelector('[data-h=in]').value);
        card.querySelectorAll('[data-h]').forEach(i => i.addEventListener('input', () => {
          const t = read();
          if (t === '') delete p().values.height; else p().values.height = t;
          setWarn(t);
          touch();
        }));
      } else {
        const inp = card.querySelector('[data-k]');
        inp.addEventListener('input', () => {
          const raw = inp.value;
          if (raw === '') delete p().values[id]; else p().values[id] = Number(raw);
          setWarn(raw);
          touch();
        });
      }
    });

    rootEl.querySelectorAll('[data-g][data-gf]').forEach(inp => {
      if (inp.dataset.bound) return;
      inp.dataset.bound = '1';
      inp.addEventListener('input', () => {
        const i = +inp.dataset.g, key = inp.dataset.gf;
        if (!p().garments[i]) p().garments[i] = {};
        const g = p().garments[i];
        if (key === 'type') g.type = inp.value;
        else if (inp.value === '') delete g[key];
        else g[key] = Number(inp.value);
        if (key !== 'type') {
          const wid = key === 'sleeve' ? 'gSleeve' : key === 'inseam' ? 'gInseam' : key;
          const w = warnValue(wid, inp.value, 'in');
          const el = rootEl.querySelector(`[data-gw="${i}-${key}"]`);
          if (el) { el.hidden = !w; el.textContent = w; }
        }
        touch();
      });
    });
    rootEl.querySelectorAll('[data-rmg]').forEach(b => b.onclick = () => {
      p().garments.splice(+b.dataset.rmg, 1);
      touch();
      renderMeasure(rootEl);
    });

    $('#msAddG', rootEl)?.addEventListener('click', () => {
      if (p().garments.length >= 3) return;
      if (!p().garments.length) p().garments.push({});
      if (p().garments.length < 3) p().garments.push({});
      touch();
      renderMeasure(rootEl);
    });
  }

  function refreshMeta(rootEl) {
    const sum = profileSummary(state);
    const el = $('#msMeta', rootEl);
    if (el) el.textContent = `${fmtFilled(sum)}${sum.garments ? ` · ${sum.garments} garment${sum.garments > 1 ? 's' : ''}` : ''}`;
  }

  function isEmptyVal(v) { return v === '' || v == null; }

  async function fetchProfileJson(url) {
    const res = await fetch(url, { cache: 'no-cache' });
    if (!res.ok) throw new Error('Could not load ' + url);
    return fromImportJson(await res.text());
  }

  async function fillDefaults(rootEl) {
    try {
      const data = await fetchProfileJson(DEFAULTS_URL);
      const src = data.profiles[0];
      if (!src) throw new Error('The defaults file has no profile in it.');
      const p = activeProfile(state);
      p.defaults = Array.isArray(p.defaults) ? p.defaults.slice() : [];
      p.estimated = Array.isArray(p.estimated) ? p.estimated.slice() : [];
      let n = 0;
      const mark = (key) => {
        if (!p.defaults.includes(key)) p.defaults.push(key);
        if (!p.estimated.includes(key)) p.estimated.push(key);
        if (Array.isArray(p.given)) p.given = p.given.filter(x => x !== key);
      };
      Object.entries(src.values || {}).forEach(([k, v]) => {
        if (isEmptyVal(p.values[k])) {
          p.values[k] = v;
          mark(k);
          n++;
        }
      });
      const sg = (src.garments || [])[0];
      if (sg) {
        if (!p.garments.length) p.garments.push({});
        const g = p.garments[0];
        g.defaults = Array.isArray(g.defaults) ? g.defaults.slice() : [];
        g.estimated = Array.isArray(g.estimated) ? g.estimated.slice() : [];
        const gmark = (key) => {
          if (!g.defaults.includes(key)) g.defaults.push(key);
          if (!g.estimated.includes(key)) g.estimated.push(key);
          if (Array.isArray(g.given)) g.given = g.given.filter(x => x !== key);
        };
        ['type', 'waistWidth', 'waistFinished', 'length', 'inseam', 'chestWidth', 'sleeve'].forEach(k => {
          if (sg[k] == null || sg[k] === '') return;
          if (isEmptyVal(g[k])) { g[k] = sg[k]; gmark(k); n++; }
        });
      }
      if (!p.modelId && src.modelId) p.modelId = src.modelId;
      p.updatedAt = Date.now();
      persist();
      renderMeasure(rootEl || root);
      refreshEntry();
      toast(n
        ? `Filled ${n} empty field${n > 1 ? 's' : ''} with defaults (all estimates). Existing numbers were kept.`
        : 'Nothing was empty — your numbers were left as is.');
    } catch (e) {
      toast(e.message || 'Could not load the default numbers.');
    }
  }

  async function loadTestProfile(rootEl) {
    try {
      const res = await fetch(TEST_PROFILE_URL, { cache: 'no-cache' });
      if (!res.ok) throw new Error('Could not load the test profile file.');
      const data = fromImportJson(await res.text());
      const built = data.profiles.find(x => x.id === TEST_PROFILE_ID) || data.profiles[0];
      if (!built) throw new Error('The test profile file has no profile in it.');
      const i = state.profiles.findIndex(x => x.id === built.id);
      if (i >= 0) state.profiles[i] = { ...built };
      else state.profiles.push({ ...built });
      state.activeId = built.id;
      persist();
      renderMeasure(rootEl || root);
      refreshEntry();
      toast('Test male 5’6" 130 lb loaded. Jordan was left as is.');
    } catch (e) {
      toast(e.message || 'Could not load the test profile.');
    }
  }

  function open(opts = {}) {
    if (window.Order && Order.isOpen()) Order.close({ fromHash: true });
    root = measureView();
    if (!openFlag) lastFocus = document.activeElement;
    openFlag = true;
    document.body.classList.add('measure-open');
    root.hidden = false;
    renderMeasure(root);
    if (!opts.fromHash && !isMeasureHash()) history.pushState(null, '', '#measure');
    window.scrollTo(0, 0);
    $('#msBack', root)?.focus();
  }

  function close(opts = {}) {
    if (!openFlag) return;
    openFlag = false;
    document.body.classList.remove('measure-open');
    const el = $('#measureView');
    if (el) el.hidden = true;
    const toasts = $('#msToasts');
    if (toasts) toasts.replaceChildren();
    refreshEntry();
    if (!opts.fromHash && isMeasureHash()) {
      if (typeof onClose === 'function') onClose();
      else history.back();
    }
    if (lastFocus && lastFocus.focus) try { lastFocus.focus(); } catch (_) {}
  }

  function bind(opts = {}) {
    if (opts.onClose) onClose = opts.onClose;
  }

  window.addEventListener('popstate', () => {
    if (isMeasureHash()) open({ fromHash: true });
    else if (openFlag) close({ fromHash: true });
  });
  window.addEventListener('hashchange', () => {
    if (isMeasureHash()) { if (!openFlag) open({ fromHash: true }); }
    else if (openFlag) close({ fromHash: true });
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && openFlag && !(e.target.closest && e.target.closest('input,textarea,select'))) {
      e.preventDefault();
      close();
    }
  });

  window.Measure = {
    mountEntry, open, close, isOpen: () => openFlag, isMeasureHash, bind,
    loadState, profileSummary, STORAGE_KEY,
  };
})();
