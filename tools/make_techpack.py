#!/usr/bin/env python3
"""Build a supplier tech-pack PDF from an Avata measurement-profile JSON.

Example (run from the model-gallery repo root):

    python3 tools/make_techpack.py \\
      --profile data/profiles/test-male-5ft6-130.json \\
      --garment chino \\
      --out /workspace/shared/model-gallery/techpacks/test-male-pant-techpack.pdf \\
      --previews /workspace/shared/model-gallery/techpacks/previews/test-male-pant

The profile is the same JSON the Measure screen exports (app: avata-measure).
Garment types currently implemented: chino, pant, pants, 5-pocket (all produce
a men's slim 5-pocket chino, graded from the profile's base waist and outseam).
Every inferred value is marked EST. in the pack.
"""
from __future__ import annotations

import argparse, json, shutil, subprocess, sys, tempfile
from datetime import date, datetime
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

REPO = Path(__file__).resolve().parents[1]
SHARED = Path('/workspace/shared/model-gallery')
LETTER = (8.5, 11)  # inches
CHROME = shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium')
PDFTOPPM = shutil.which('pdftoppm')

# ---------------------------------------------------------------------------
# Units / formatting
# ---------------------------------------------------------------------------
FRAC = {
    0.0: '', 0.125: '⅛', 0.25: '¼', 0.375: '⅜', 0.5: '½',
    0.625: '⅝', 0.75: '¾', 0.875: '⅞',
}

def inch(v, prec=3):
    """Format a number of inches with Unicode fractions, or EST. blank if None."""
    if v is None or v == '':
        return '—'
    x = float(v)
    sign = '−' if x < 0 else ''
    x = abs(round(x * 8) / 8)  # nearest 1/8
    whole = int(x)
    frac = round(x - whole, 3)
    glyph = FRAC.get(frac)
    if glyph is None:
        # fallback to 2 decimals
        body = f'{x:.2f}'.rstrip('0').rstrip('.')
        return sign + body
    if whole == 0 and glyph:
        return sign + glyph
    return sign + (f'{whole}{glyph}' if glyph else f'{whole}')


def delta(v):
    """Grade step, with a leading + for positives."""
    if v == 0 or v == 0.0:
        return '0'
    s = inch(v)
    return '+' + s if float(v) > 0 and not s.startswith('−') else s


def esc(s):
    return (str(s) if s is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
def load_profile(path: Path) -> dict:
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and data.get('profiles'):
        pid = data.get('activeId')
        prof = next((p for p in data['profiles'] if p.get('id') == pid), data['profiles'][0])
    elif isinstance(data, dict) and (data.get('values') or data.get('name')):
        prof = data
    else:
        raise SystemExit(f'Not an avata-measure profile: {path}')
    prof.setdefault('values', {})
    prof.setdefault('garments', [])
    prof.setdefault('given', [])
    prof.setdefault('estimated', [])
    return prof


def givenp(prof, key) -> bool:
    return key in (prof.get('given') or [])


def first_garment(prof) -> dict:
    gs = prof.get('garments') or []
    return gs[0] if gs else {}


# ---------------------------------------------------------------------------
# Color sampling + frame prep
# ---------------------------------------------------------------------------
PANTONE_NEAR = [
    # (hex, name) approximate TCX references for sampled greys
    ((156, 152, 151), '16-3801 TCX Wind Chime'),
    ((148, 145, 142), '16-1405 TCX Atmosphere'),
    ((127, 123, 118), '17-1502 TCX Plaza Taupe'),
    ((106, 102, 96), '18-0601 TCX Fallen Rock'),
    ((28, 28, 30), '19-3911 TCX Black Beauty'),
]


def nearest_pantone(rgb):
    r, g, b = rgb
    best, bd = PANTONE_NEAR[0], 1e9
    for c, name in PANTONE_NEAR:
        d = (r - c[0]) ** 2 + (g - c[1]) ** 2 + (b - c[2]) ** 2
        if d < bd:
            best, bd = (c, name), d
    return best[1]


def _is_bg(pix):
    r, g, b = pix
    return r > 245 and g > 245 and b > 245


def sample_garment_color(im: Image.Image):
    w, h = im.size
    px = im.convert('RGB').load()
    cols = []
    for y in range(int(h * 0.45), int(h * 0.78), 4):
        for x in range(int(w * 0.30), int(w * 0.70), 4):
            r, g, b = px[x, y]
            if _is_bg((r, g, b)):
                continue
            if r - b > 25 and r - g > 15:  # skin-ish
                continue
            if 50 < r < 210 and abs(r - g) < 20 and abs(g - b) < 20:
                cols.append((r, g, b))
    if not cols:
        return (156, 152, 151)
    cols.sort()
    mid = cols[len(cols) // 2]
    return mid


def find_subject(im: Image.Image):
    rgb = im.convert('RGB')
    w, h = rgb.size
    px = rgb.load()
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if not _is_bg(px[x, y]):
                xs.append(x); ys.append(y)
    if not xs:
        return (0, 0, w, h)
    return min(xs), min(ys), max(xs), max(ys)


def prep_frames(assets: Path, model_id: str, out_dir: Path, angles=None):
    """Copy/convert hi frames to JPEG in out_dir. Returns {angle: path}."""
    angles = angles or (0, 45, 90, 135, 180, 225, 270, 315)
    src_dir = assets / model_id / 'base' / 'hi'
    if not src_dir.is_dir():
        # allow a flat folder of 000.webp etc.
        src_dir = assets
    out_dir.mkdir(parents=True, exist_ok=True)
    found = {}
    for a in angles:
        name = f'{int(a):03d}'
        src = None
        for ext in ('.webp', '.jpg', '.jpeg', '.png'):
            p = src_dir / f'{name}{ext}'
            if p.is_file():
                src = p
                break
        if not src:
            raise SystemExit(f'Missing {model_id} frame {name} under {src_dir}')
        dest = out_dir / f'{name}.jpg'
        if Image is None:
            shutil.copy(src, dest.with_suffix(src.suffix))
            found[int(a)] = dest.with_suffix(src.suffix)
            continue
        im = Image.open(src).convert('RGB')
        im.save(dest, 'JPEG', quality=92, optimize=True)
        found[int(a)] = dest
    return found


def crop_jpeg(src: Path, box, dest: Path, pad_white=True):
    im = Image.open(src).convert('RGB')
    w, h = im.size
    x0, y0, x1, y1 = box
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    crop = im.crop((x0, y0, x1, y1))
    crop.save(dest, 'JPEG', quality=92, optimize=True)
    return dest


def pantone_swatch(rgb, dest: Path, size=240):
    if Image is None:
        return None
    im = Image.new('RGB', (size, size), rgb)
    im.save(dest, 'PNG')
    return dest


# ---------------------------------------------------------------------------
# POM
# ---------------------------------------------------------------------------
def chino_pom(prof: dict):
    """POM chart for a men's slim 5-pocket chino. Base = profile garment waist / outseam."""
    g = first_garment(prof)
    v = prof.get('values') or {}
    waist = float(g.get('waistFinished') or ((g.get('waistWidth') or 0) * 2) or 31)
    outseam = float(g.get('length') or 35)
    front_rise = float(g.get('frontRise') or v.get('frontRise') or 10.25)
    back_rise = float(g.get('backRise') or v.get('backRise') or 14.75)
    inseam = float(g.get('inseam') or (outseam - front_rise + 0.25))
    hip_body = float(v.get('hip') or 36.5)
    thigh_body = float(v.get('thigh') or 20.75)
    knee_body = float(v.get('knee') or 14.25)
    # slim ease (EST.)
    hip = hip_body + 2.0
    thigh = thigh_body + 1.25
    knee = knee_body + 1.5
    opening = 14.5
    wb = 1.5
    loop = 2.0
    fly = 4.25
    pk_open = 5.5
    bk_w, bk_h = 5.5, 6.0

    # sizes across 28–36, with the profile waist as the base (even if odd, e.g. 31)
    sizes = [28, 30]
    if waist not in sizes:
        sizes.append(int(waist) if waist == int(waist) else waist)
    sizes += [32, 34, 36]
    # unique, sorted, keep base even if already in list
    sizes = sorted(set(float(s) for s in sizes))

    def grade(base, step, sz):
        return base + step * (sz - waist)

    rows = [
        # code, name, how, base, step per 1" waist, given?
        ('A', 'Waist, relaxed', 'Circumference at the top of the waistband, unstretched, buttoned.', waist, 1.0, True),
        ('B', 'Seat / hip', 'Circumference 7 in below the top of the waistband, through the seat.', hip, 1.0, False),
        ('C', 'Thigh', 'Circumference 1 in below the crotch, perpendicular to the grain.', thigh, 0.5, False),
        ('D', 'Knee', 'Circumference 13 in below the crotch, perpendicular to the grain.', knee, 0.375, False),
        ('E', 'Leg opening', 'Circumference at the hem, unstretched.', opening, 0.25, False),
        ('F', 'Front rise', 'From the top of the waistband at center front, over the fork, to the crotch join (includes WB).', front_rise, 0.25, False),
        ('G', 'Back rise', 'From the top of the waistband at center back, over the seat, to the crotch join (includes WB).', back_rise, 0.25, False),
        ('H', 'Inseam', 'Crotch join to the hem, along the inside leg.', inseam, 0.0, False),
        ('I', 'Outseam / total length', 'Top of the waistband at the side seam to the hem.', outseam, 0.0, True),
        ('J', 'Waistband height', 'Finished height of the waistband, edge to edge.', wb, 0.0, False),
        ('K', 'Belt-loop length', 'Finished length of a loop, end to end, before bartack.', loop, 0.0, False),
        ('L', 'Fly length', 'From the waistband join to the fly bottom bartack.', fly, 0.125, False),
        ('M', 'Front-pocket opening', 'Along the pocket mouth, lip to lip.', pk_open, 0.125, False),
        ('N', 'Back-pocket width', 'Finished width of the patch, at the top edge.', bk_w, 0.125, False),
        ('O', 'Back-pocket height', 'Finished height of the patch, at the center.', bk_h, 0.125, False),
    ]
    # tolerances
    tol = {
        'A': '±¼', 'B': '±⅜', 'C': '±¼', 'D': '±¼', 'E': '±¼',
        'F': '±¼', 'G': '±¼', 'H': '±¼', 'I': '±¼', 'J': '±⅛',
        'K': '±⅛', 'L': '±⅛', 'M': '±⅛', 'N': '±⅛', 'O': '±⅛',
    }
    chart = []
    for code, name, how, base, step, is_given in rows:
        rec = {
            'code': code, 'name': name, 'how': how, 'base': base, 'step': step,
            'given': is_given, 'tol': tol[code],
            'sizes': {sz: grade(base, step, sz) for sz in sizes},
        }
        chart.append(rec)
    return {
        'kind': 'slim 5-pocket chino',
        'base_waist': waist,
        'base_outseam': outseam,
        'sizes': sizes,
        'rows': chart,
        'notes': (
            f'Base size is US waist {inch(waist)} with a {inch(outseam)} in outseam (length held across the waist range). '
            f'A and I are taken from the measurement profile (given). All other POMs are estimated from the profile’s body '
            f'measures plus slim ease, and from a mid-rise 5-pocket chino construction. Inseam is held with the outseam; '
            f'rise grades ¼ in per waist inch. Do not cut a production run from these numbers alone.'
        ),
    }


# ---------------------------------------------------------------------------
# Flats (illustrative SVG)
# ---------------------------------------------------------------------------
def chino_flats_svg(accent='#6A6660'):
    # 11 x 7.2 in view, two views
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 720" fill="none" stroke="#161616" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
  <text x="140" y="28" fill="#161616" stroke="none" font-family="Liberation Sans,Helvetica,Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="2">FRONT</text>
  <text x="700" y="28" fill="#161616" stroke="none" font-family="Liberation Sans,Helvetica,Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="2">BACK</text>

  <!-- FRONT pant -->
  <g transform="translate(40,40)">
    <!-- waistband -->
    <path d="M150 20 H350 L348 52 H152 Z"/>
    <path d="M152 36 H348" stroke-width="0.9"/>
    <!-- body -->
    <path d="M152 52 L138 150 L118 430 L130 640 H230 L250 250 L270 640 H370 L382 430 L362 150 L348 52"/>
    <!-- fly -->
    <path d="M250 52 L250 148" stroke-dasharray="4 3"/>
    <path d="M250 52 L262 64 L262 130" stroke-width="1.3"/>
    <!-- front pockets -->
    <path d="M152 70 L200 70 L188 150 L152 128 Z"/>
    <path d="M348 70 L300 70 L312 150 L348 128 Z"/>
    <!-- coin pocket -->
    <rect x="305" y="78" width="28" height="22"/>
    <!-- belt loops: 5 visible on front (center, 2 mid, 2 side) -->
    <rect x="246" y="16" width="8" height="40" fill="#fff"/>
    <rect x="168" y="16" width="8" height="40" fill="#fff"/>
    <rect x="324" y="16" width="8" height="40" fill="#fff"/>
    <rect x="148" y="16" width="7" height="40" fill="#fff"/>
    <rect x="345" y="16" width="7" height="40" fill="#fff"/>
    <!-- hem -->
    <path d="M130 625 H230" stroke-width="1.1"/>
    <path d="M270 625 H370" stroke-width="1.1"/>
    <!-- callouts -->
    <g fill="#161616" stroke="none" font-family="Liberation Sans,Helvetica,Arial,sans-serif" font-size="12" font-weight="700">
      <text x="250" y="10" text-anchor="middle">A</text>
      <text x="80" y="200">B</text>
      <text x="70" y="280">C</text>
      <text x="70" y="470">D</text>
      <text x="80" y="655">E</text>
      <text x="266" y="118">F / L</text>
      <text x="400" y="40">J</text>
      <text x="400" y="100">M</text>
      <text x="400" y="630">I</text>
      <text x="80" y="540">H</text>
    </g>
    <g stroke="#7a3f0c" stroke-width="1">
      <path d="M150 10 H350"/>
      <path d="M100 200 H138"/>
      <path d="M90 280 H125"/>
      <path d="M90 470 H122"/>
      <path d="M100 655 H130"/>
      <path d="M90 540 L200 540"/>
      <path d="M370 630 H400"/>
    </g>
  </g>

  <!-- BACK pant -->
  <g transform="translate(560,40)">
    <path d="M150 20 H350 L348 52 H152 Z"/>
    <path d="M152 36 H348" stroke-width="0.9"/>
    <path d="M152 52 L138 150 L118 430 L130 640 H230 L250 250 L270 640 H370 L382 430 L362 150 L348 52"/>
    <!-- CB seam -->
    <path d="M250 52 L250 250" stroke-dasharray="4 3"/>
    <!-- yoke -->
    <path d="M152 52 Q250 88 348 52" stroke-width="1.3"/>
    <!-- back patches -->
    <rect x="165" y="100" width="70" height="78" rx="1"/>
    <rect x="265" y="100" width="70" height="78" rx="1"/>
    <path d="M178 108 H222" stroke-width="1.1"/>
    <path d="M278 108 H322" stroke-width="1.1"/>
    <!-- buttons on pockets -->
    <circle cx="200" cy="118" r="3.2"/>
    <circle cx="300" cy="118" r="3.2"/>
    <!-- belt loops -->
    <rect x="246" y="16" width="8" height="40" fill="#fff"/>
    <rect x="168" y="16" width="8" height="40" fill="#fff"/>
    <rect x="324" y="16" width="8" height="40" fill="#fff"/>
    <rect x="148" y="16" width="7" height="40" fill="#fff"/>
    <rect x="345" y="16" width="7" height="40" fill="#fff"/>
    <path d="M130 625 H230" stroke-width="1.1"/>
    <path d="M270 625 H370" stroke-width="1.1"/>
    <g fill="#161616" stroke="none" font-family="Liberation Sans,Helvetica,Arial,sans-serif" font-size="12" font-weight="700">
      <text x="250" y="12" text-anchor="middle">G</text>
      <text x="200" y="94" text-anchor="middle">N</text>
      <text x="248" y="140">O</text>
      <text x="400" y="36">K</text>
    </g>
    <g stroke="#7a3f0c" stroke-width="1">
      <path d="M353 36 H400"/>
    </g>
  </g>
</svg>'''


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
CSS = r'''
@font-face{font-family:Sans;src:url("LiberationSans-Regular.ttf");font-weight:400;}
@font-face{font-family:Sans;src:url("LiberationSans-Bold.ttf");font-weight:700;}
@font-face{font-family:Sans;src:url("LiberationSans-Italic.ttf");font-weight:400;font-style:italic;}
@font-face{font-family:Sans;src:url("LiberationSans-BoldItalic.ttf");font-weight:700;font-style:italic;}
@font-face{font-family:Serif;src:url("LiberationSerif-Regular.ttf");font-weight:400;}
@font-face{font-family:Serif;src:url("LiberationSerif-Bold.ttf");font-weight:700;}
:root{--ink:#161616;--muted:#5c5c57;--rule:#d0cec8;--wash:#f3f2ee;--est:#7a3f0c;--paper:#fff;}
*{box-sizing:border-box;margin:0;padding:0;}
@page{size:letter;margin:0;}
html,body{background:#fff;color:var(--ink);font-family:Sans,Helvetica,Arial,sans-serif;font-size:8.4pt;line-height:1.38;}
.page{width:8.5in;height:11in;padding:0.42in 0.48in 0.38in;position:relative;page-break-after:always;overflow:hidden;background:#fff;}
.page:last-child{page-break-after:auto;}
header.hdr{border-bottom:1.6pt solid var(--ink);padding-bottom:6pt;margin-bottom:10pt;}
header.hdr .row1{display:flex;justify-content:space-between;align-items:baseline;}
header.hdr .brand{font-weight:700;letter-spacing:0.18em;font-size:8.5pt;}
header.hdr .doc{font-weight:700;letter-spacing:0.16em;font-size:8.5pt;}
header.hdr .stno{font-weight:700;letter-spacing:0.08em;font-size:10pt;}
header.hdr .row2{display:flex;justify-content:space-between;margin-top:3pt;color:var(--muted);font-size:7.5pt;letter-spacing:0.02em;}
footer.ftr{position:absolute;left:0.48in;right:0.48in;bottom:0.22in;border-top:0.6pt solid var(--rule);padding-top:4pt;display:flex;justify-content:space-between;gap:10pt;font-size:6.6pt;color:var(--muted);line-height:1.3;}
footer.ftr .est{color:var(--est);flex:1;text-align:center;}
h1{font-family:Serif,Georgia,serif;font-weight:700;font-size:22pt;line-height:1.05;letter-spacing:-0.01em;}
h2{font-size:10.5pt;letter-spacing:0.08em;font-weight:700;margin:0 0 7pt;border-bottom:0.8pt solid var(--ink);padding-bottom:3pt;}
h3{font-size:8pt;letter-spacing:0.1em;font-weight:700;margin:8pt 0 4pt;}
p{margin:0 0 5pt;}
.muted{color:var(--muted);}
.est{color:var(--est);}
.badge{display:inline-block;border:0.7pt solid var(--est);color:var(--est);font-size:6.5pt;font-weight:700;letter-spacing:0.08em;padding:1pt 4pt;vertical-align:1px;}
.badge.given{border-color:var(--ink);color:var(--ink);}
table{width:100%;border-collapse:collapse;font-size:7.4pt;}
th,td{border:0.45pt solid #c8c6c0;padding:3.2pt 4.5pt;vertical-align:top;}
th{background:var(--wash);font-weight:700;text-align:center;letter-spacing:0.03em;}
td.l{text-align:left;}
td.c,th.c{text-align:center;white-space:nowrap;}
td.base,th.base{background:#ebeae5;font-weight:700;}
.note{font-size:7.2pt;color:var(--muted);line-height:1.4;}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:10pt;}
.cap{font-size:7pt;color:var(--muted);margin-top:3pt;text-align:center;letter-spacing:0.02em;}
img{display:block;}
.fig{background:var(--wash);border:0.4pt solid var(--rule);}
.cover-top{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2.2pt solid var(--ink);padding-bottom:8pt;margin-bottom:14pt;}
.cover-brand{font-weight:700;letter-spacing:0.22em;font-size:9.5pt;}
.cover-kicker{letter-spacing:0.18em;font-size:8pt;font-weight:700;margin-bottom:4pt;}
.meta{width:100%;border-collapse:collapse;margin-top:8pt;margin-bottom:8pt;}
.meta th,.meta td{border:none;border-bottom:0.45pt solid var(--rule);padding:3.2pt 6pt 3.2pt 0;text-align:left;background:none;font-weight:400;}
.meta th{width:1.55in;font-weight:700;letter-spacing:0.08em;font-size:7pt;color:var(--muted);text-transform:uppercase;}
.meta td{font-size:9pt;}
.hero-wrap{display:grid;grid-template-columns:1.15fr 0.85fr;gap:14pt;align-items:end;}
.hero-wrap .hero{background:#f7f6f3;border:0.4pt solid var(--rule);padding:8pt 8pt 4pt;text-align:center;}
.hero-wrap .hero img{width:100%;height:4.85in;object-fit:contain;object-position:center top;}
.strip{display:grid;grid-template-columns:1fr 1fr;gap:6pt;}
.strip .cell{background:#f7f6f3;border:0.4pt solid var(--rule);padding:4pt 4pt 2pt;}
.strip img{width:100%;height:2.28in;object-fit:contain;object-position:center top;}
.disclaimer{margin-top:8pt;border:0.7pt solid var(--est);padding:6pt 8pt;font-size:7.2pt;color:var(--est);line-height:1.4;}
.views{display:grid;grid-template-columns:repeat(4,1fr);gap:7pt 6pt;}
.views .cell{background:#f7f6f3;border:0.4pt solid var(--rule);padding:5pt 4pt 3pt;}
.views img{width:100%;height:3.55in;object-fit:contain;object-position:center top;}
.details{display:grid;grid-template-columns:1fr 1fr 1fr;grid-template-rows:auto auto;gap:8pt 7pt;}
.details .cell{background:#f7f6f3;border:0.4pt solid var(--rule);padding:4pt 4pt 3pt;}
.details img{width:100%;height:2.55in;object-fit:contain;object-position:center;background:#f7f6f3;}
.sign{display:grid;grid-template-columns:1fr 1fr;gap:8pt 12pt;margin-top:6pt;}
.sign .box{border:0.6pt solid var(--ink);padding:7pt 8pt 6pt;height:0.95in;}
.sign .box .role{font-weight:700;letter-spacing:0.1em;font-size:7pt;margin-bottom:6pt;}
.sign .box .line{border-bottom:0.45pt solid #888;height:16pt;margin:3pt 0 2pt;font-size:7.5pt;color:var(--muted);}
.swatch-row{display:flex;gap:10pt;align-items:stretch;margin:6pt 0 8pt;}
.swatch{width:1.15in;height:0.85in;border:0.5pt solid #aaa;}
.swatch-info{flex:1;font-size:7.6pt;}
.lbl-grid{display:grid;grid-template-columns:1.3in 1fr;gap:4pt 8pt;font-size:7.5pt;}
.lbl-grid b{letter-spacing:0.04em;}
ol.steps{margin:0 0 6pt 16pt;}
ol.steps li{margin:0 0 4pt;padding:0;}
.nowrap{white-space:nowrap;}
'''


def hdr(style, page_title, season='SS27 Prototype'):
    return f'''  <header class="hdr">
    <div class="row1"><span class="brand">ATELIER 360</span><span class="doc">TECHNICAL PACKAGE</span><span class="stno">{esc(style)}</span></div>
    <div class="row2"><span>{esc(page_title)}</span><span>{esc(season)}</span></div>
  </header>'''


def ftr(style, page, total, extra='Items marked EST. or * are estimates, not physical sample measurements.'):
    return f'''  <footer class="ftr"><span>Atelier 360  ·  Confidential, for manufacturing use</span><span class="est">{esc(extra)}</span><span>{page:02d} / {total:02d}</span></footer>'''


def build_html(ctx: dict) -> str:
    p, pom, style = ctx['profile'], ctx['pom'], ctx['style']
    v = p.get('values') or {}
    g = first_garment(p)
    name = p.get('name') or 'Fit model'
    ht = v.get('height')
    ht_s = f"{int(ht)//12} ft {inch(ht % 12)} in" if ht else '—'
    wt = v.get('weight')
    pages = ctx['pages']
    rgb = ctx['rgb']
    hexcol = '#%02X%02X%02X' % rgb
    pantone = ctx['pantone']
    imgs = ctx['imgs']  # relative names
    angle_labels = {0: 'Front', 45: 'Front ¾ · left', 90: 'Left side', 135: 'Back ¾ · left',
                    180: 'Back', 225: 'Back ¾ · right', 270: 'Right side', 315: 'Front ¾ · right'}

    def src(key):
        return esc(imgs[key])

    # POM table
    size_heads = ''.join(
        f'<th class="c{" base" if sz == pom["base_waist"] else ""}">W{inch(sz)}</th>'
        for sz in pom['sizes']
    )
    pom_rows = []
    for row in pom['rows']:
        flag = '<span class="badge given">GIVEN</span>' if row['given'] else '<span class="badge">EST.</span>'
        cells = ''.join(
            f'<td class="c{" base" if sz == pom["base_waist"] else ""}">{inch(row["sizes"][sz])}</td>'
            for sz in pom['sizes']
        )
        pom_rows.append(
            f'<tr><td class="c"><b>{row["code"]}</b></td><td class="l">{esc(row["name"])} {flag}<div class="note">{esc(row["how"])}</div></td>'
            f'{cells}<td class="c">{row["tol"]}</td></tr>'
        )
    size_label = ' / '.join(f'W{inch(s)}' + (' (base)' if s == pom['base_waist'] else '') for s in pom['sizes'])

    views = []
    for a in (0, 45, 90, 135, 180, 225, 270, 315):
        views.append(
            f'<div class="cell"><img src="{src(f"view-{a:03d}")}" alt="{angle_labels[a]}"><div class="cap">{angle_labels[a]}  ·  {a}°</div></div>'
        )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{esc(style)} Slim 5-Pocket Chino — Technical Package</title>
<style>{CSS}</style>
</head>
<body>

<!-- PAGE 1 COVER -->
<section class="page">
  <div class="cover-top">
    <div>
      <div class="cover-brand">ATELIER 360</div>
      <div class="muted" style="margin-top:2pt;letter-spacing:0.08em;font-size:7.5pt;">APPAREL  ·  TECHNICAL PACKAGE</div>
    </div>
    <div style="text-align:right;">
      <div style="font-weight:700;font-size:14pt;letter-spacing:0.06em;">{esc(style)}</div>
      <div class="muted" style="font-size:7.5pt;margin-top:2pt;">23 November 2026</div>
    </div>
  </div>
  <div class="cover-kicker">STYLE</div>
  <h1>Slim 5-Pocket Chino</h1>
  <p class="muted" style="margin-top:4pt;font-size:9.5pt;">Men’s ankle-length slim chino  ·  Colorway Mid Grey  ·  Zip fly, five pockets</p>
  <table class="meta">
    <tr><th>Style number</th><td>{esc(style)}</td></tr>
    <tr><th>Season</th><td>SS27 Prototype</td></tr>
    <tr><th>Designer</th><td>Jordan Salazar</td></tr>
    <tr><th>Date</th><td>23 November 2026</td></tr>
    <tr><th>Fit model</th><td>{esc(name)}, Model 6 (exact-28), slim adult male, {ht_s}, {inch(wt) if wt else '—'} lb.
      Body waist {inch(v.get('waist'))} in, hip {inch(v.get('hip'))} in, floor inseam {inch(v.get('inseam'))} in.
      {'Height and weight GIVEN; other body measures EST.' if True else ''}</td></tr>
    <tr><th>Base size</th><td>US waist {inch(pom['base_waist'])}  ·  outseam {inch(pom['base_outseam'])} in
      <span class="badge given">GIVEN</span>  ·  graded to waist 28–36</td></tr>
    <tr><th>Reference garment</th><td>{esc(g.get('type') or 'slim chino')}, finished waist {inch(g.get('waistFinished') or pom['base_waist'])} in,
      outseam {inch(g.get('length') or pom['base_outseam'])} in (given); garment inseam {inch(g.get('inseam'))} in <span class="badge">EST.</span></td></tr>
  </table>
  <div class="hero-wrap">
    <div class="hero"><img src="{src('view-000')}" alt="Fit model front"><div class="cap">Fit model, front  ·  Model 6, grey set (existing gallery asset)</div></div>
    <div class="strip">
      <div class="cell"><img src="{src('view-090')}" alt="Left side"><div class="cap">Left side  ·  90°</div></div>
      <div class="cell"><img src="{src('view-180')}" alt="Back"><div class="cap">Back  ·  180°</div></div>
    </div>
  </div>
  <div class="disclaimer"><b>READ THIS FIRST.</b> This pack is driven by a test measurement profile and photograph references of a digital/fit-model image (Model 6 in a grey long-sleeve and pant), not from a physical sample or a graded pattern. The photographs show a similar grey pant on the fit model; they are image references, not the proto sample. Fabric, stitch, colour-standard name, trim and every measurement not marked GIVEN is a <b>proposal or estimate</b> for the supplier to confirm on the first proto (waist {inch(pom['base_waist'])}, outseam {inch(pom['base_outseam'])} in). The {inch(pom['base_outseam'])} in outseam on this 5 ft 6 in body is an ankle-length hem, about 4 in above the floor. Do not cut a production run from these numbers alone.</div>
  {ftr(style, 1, pages, 'Confidential, for manufacturing use')}
</section>

<!-- PAGE 2 REFERENCES -->
<section class="page">
  {hdr(style, 'Image references  ·  8-view fit model')}
  <p class="note" style="margin-bottom:8pt;">Gallery Model 6 (exact-28), Base, grey fitted set. These are the eight shipped views, used here as a fit-model reference only. The pant in the photographs is the existing grey set, not a stitched proto of {esc(style)}. Views are labeled by camera angle (0° = front).</p>
  <div class="views">{''.join(views)}</div>
  {ftr(style, 2, pages)}
</section>

<!-- PAGE 3 DETAILS -->
<section class="page">
  {hdr(style, 'Image references  ·  pant detail crops')}
  <p class="note" style="margin-bottom:8pt;">Crops from the Model 6 grey-set frames, for waist, rise, side seam and hem reference. Construction of {esc(style)} (5-pocket, zip fly, belt loops) is specified on the flats and construction pages — some of those details are not visible, or differ, in this existing set. Crops are framed from the photograph, not from a physical sample. <span class="badge">EST.</span> as a construction reference.</p>
  <div class="details">
    <div class="cell"><img src="{src('detail-waist-front')}" alt="Front waist"><div class="cap">Front waist and fly area  ·  0°</div></div>
    <div class="cell"><img src="{src('detail-hip')}" alt="Hip and thigh"><div class="cap">Seat / thigh  ·  0°</div></div>
    <div class="cell"><img src="{src('detail-hem-front')}" alt="Front hem"><div class="cap">Hem, front  ·  0°</div></div>
    <div class="cell"><img src="{src('detail-side')}" alt="Side outseam"><div class="cap">Side seam / outseam  ·  90°</div></div>
    <div class="cell"><img src="{src('detail-back-waist')}" alt="Back waist"><div class="cap">Back waist and seat  ·  180°</div></div>
    <div class="cell"><img src="{src('detail-hem-back')}" alt="Back hem"><div class="cap">Hem, back  ·  180°</div></div>
  </div>
  {ftr(style, 3, pages)}
</section>

<!-- PAGE 4 FLATS -->
<section class="page">
  {hdr(style, 'Illustrative flats')}
  <p class="note" style="margin-bottom:6pt;">Clean line drawings made for this pack — <b>not a pattern and not to scale</b>. They describe construction intent only (slim 5-pocket chino, zip fly, 1½ in waistband, six belt loops, slant front pockets with a coin pocket, two back patch pockets with button). Callout letters match the POM chart on page 7.</p>
  <div class="fig" style="padding:8pt 6pt 4pt;">
    <img src="{src('flats')}" alt="Front and back flats" style="width:100%;height:8.15in;object-fit:contain;">
  </div>
  {ftr(style, 4, pages)}
</section>

<!-- PAGE 5 BOM -->
<section class="page">
  {hdr(style, 'Bill of materials')}
  <p class="note" style="margin-bottom:6pt;">All materials below are <span class="badge">EST.</span> proposed to match the mid-grey hand of the fit-model photographs and a classic chino. Supplier to submit a lab dip, fabric swatch (weight, stretch, recovery, shrinkage) and trim card before proto cutting.</p>
  <table>
    <tr><th>Item</th><th>Used on</th><th>Description</th><th>Colour / code</th><th>Qty / base size</th><th>Status</th></tr>
    <tr>
      <td class="l">1. Shell fabric</td>
      <td class="l">Body, WB, loops, pocket welts, patches</td>
      <td class="l">Cotton chino twill, ~7.5–8 oz/yd² (250–270 g/m²), 1/2 twill, slight mechanical stretch optional (98/2 cotton-elastane). Washed, sueded or peached face acceptable. 58–60 in usable width.</td>
      <td class="l">{hexcol}  ·  approx. {esc(pantone)}</td>
      <td class="c">Yield EST. ~1.15–1.35 yd @ 60 in, waist {inch(pom['base_waist'])}</td>
      <td class="est">EST.</td>
    </tr>
    <tr>
      <td class="l">2. Pocketing</td>
      <td class="l">Front pocket bags, coin bag</td>
      <td class="l">Cotton or poly-cotton pocketing, 4–5 oz/yd², matching or slightly lighter grey.</td>
      <td class="l">Self-tone grey  ·  EST.</td>
      <td class="c">~0.25 yd</td>
      <td class="est">EST.</td>
    </tr>
    <tr>
      <td class="l">3. Fly zipper</td>
      <td class="l">Center-front fly</td>
      <td class="l">Closed-end coil zipper, ~4½ in, colour-matched to shell, with auto-lock slider. Brand TBD (YKK or equal).</td>
      <td class="l">Mid grey  ·  EST.</td>
      <td class="c">1</td>
      <td class="est">EST. / TBD</td>
    </tr>
    <tr>
      <td class="l">4. Waistband hook &amp; bar + button</td>
      <td class="l">WB closure</td>
      <td class="l">Interior hook and bar at the WB extension, plus one 18-ligne corozo or recycled-poly button at the CF, self-tone or horn-look grey.</td>
      <td class="l">Self-tone  ·  EST.</td>
      <td class="c">1 hook/bar + 1 button (plus 2 pocket buttons)</td>
      <td class="est">EST. / TBD</td>
    </tr>
    <tr>
      <td class="l">5. Thread</td>
      <td class="l">All seams, topstitch, bartacks</td>
      <td class="l">Spun poly or poly-core, Tex 40 seams / Tex 60 topstitch, matched to shell. Bartacks same or one shade darker.</td>
      <td class="l">Matched to {hexcol}  ·  EST.</td>
      <td class="c">As needed</td>
      <td class="est">EST.</td>
    </tr>
    <tr>
      <td class="l">6. Labels</td>
      <td class="l">CB waistband, care, hangtag</td>
      <td class="l">Woven brand label at CB WB, printed care/content at left WB facing, hangtag with style, colourway, waist and inseam.</td>
      <td class="l">See page 8</td>
      <td class="c">1 set</td>
      <td class="est">EST. / TBD</td>
    </tr>
    <tr>
      <td class="l">7. Size sticker + polybag</td>
      <td class="l">Packing</td>
      <td class="l">Clear polybag with size sticker (waist × outseam / inseam) and style number.</td>
      <td class="l">—</td>
      <td class="c">1</td>
      <td class="est">EST.</td>
    </tr>
  </table>
  <p class="note" style="margin-top:8pt;">No contrast topstitch is specified; use a matched thread. No rivets. Yield and bag size are rough planning figures only. Colour standard is a photograph sample, not a certified lab dip — nearest Pantone TCX is approximate.</p>
  {ftr(style, 5, pages)}
</section>

<!-- PAGE 6 CONSTRUCTION -->
<section class="page">
  {hdr(style, 'Construction')}
  <p class="note" style="margin-bottom:6pt;">All methods are <span class="badge">EST.</span> proposed for a clean, mid-weight chino. Supplier may recommend an equivalent method; confirm on the first proto. Seam allowance ⅜ in unless noted. Stitch 10–12 SPI lockstitch; 8–9 SPI topstitch.</p>
  <div class="grid-2">
    <div>
      <h3>WAISTBAND AND FLY</h3>
      <ol class="steps">
        <li>1.5 in finished waistband, fused with a mid-weight cotton or poly fusible, folded, with a ¼ in extension and interior hook-and-bar. One button at CF through the shell.</li>
        <li>Six belt loops of self shell, ⅜ in finished width, 2 in finished length, bartacked at the top of the WB and at the lower WB join: one either side of center back, one at each side seam, and one at each side front, evenly spaced.</li>
        <li>French or JL fly with a 4¼ in colour-matched coil zipper (base size), zipper tape caught in the fly shield. J-stitch through the fly, bartack at the fly bottom.</li>
      </ol>
      <h3>POCKETS</h3>
      <ol class="steps">
        <li>Front: slanted side pockets, 5½ in mouth, self facing, pocketing bag to mid-thigh. Coin pocket 3 in wide × 2¾ in deep, set in the right-front pocket (wearer’s right).</li>
        <li>Back: two applied patch pockets, 5½ × 6 in, ¼ in double-needle hem at the mouth, one button and buttonhole at the center of each. Topstitch ¼ in around the pocket. Optional ⅛ in welt at the mouth if the supplier prefers a cleaner chino look — confirm on proto; default is a patch with a clean hem.</li>
        <li>Bartack at all pocket-mouth ends and at the coin-pocket corners.</li>
      </ol>
    </div>
    <div>
      <h3>SEAMS, HEM, PRESSING</h3>
      <ol class="steps">
        <li>Side seams and inseams: 5-thread safety stitch or ⅜ in clean-finish overlock plus a ⅛ in topstitch on the side seam (outseam) if wanted. Default: overlocked and pressed, no outseam topstitch, for a quieter chino.</li>
        <li>Seat seam: lapped or pressed-open and topstitched ¼ in to the wearer’s left, bartacked at the crotch join.</li>
        <li>Crotch join reinforced with a bartack or a small crotch stay of pocketing.</li>
        <li>Hem: 1¼ in single-fold clean hem, lockstitch, unblind. No cuff. Outseam 35 in from the top of the WB to the hem on the base size — this is an ankle length on the 5 ft 6 in fit model.</li>
        <li>Press: crease from hem to mid-thigh only (optional, confirm); WB, pockets and fly sharp. Garment washed only if the shell is a wash finish — otherwise a clean press.</li>
      </ol>
      <h3>TOLERANCE AND QUALITY</h3>
      <p>POM tolerances are on page 7. Shade within the lab dip. No puckering at the fly, WB or pocket mouths. Loop spacing even. Topstitch SPI consistent. Clip and grade the WB and fly curves. Needle size 80/12 or 90/14 as the fabric requires.</p>
    </div>
  </div>
  {ftr(style, 6, pages)}
</section>

<!-- PAGE 7 POM -->
<section class="page">
  {hdr(style, 'Points of measure  ·  inches')}
  <p class="note" style="margin-bottom:6pt;">US waist sizes {esc(size_label)}. Base column is shaded. A (waist) and I (outseam) are <span class="badge given">GIVEN</span> from the test profile’s reference chino. Every other POM is <span class="badge">EST.</span> Lengths (H, I, J, K) are held across the waist range; rises and circumferences grade from the base. Measure the finished garment laid flat, then double for circumferences (A–E).</p>
  <table>
    <tr>
      <th>POM</th><th class="l">Point of measure</th>
      {size_heads}
      <th>Tol.</th>
    </tr>
    {''.join(pom_rows)}
  </table>
  <p class="note" style="margin-top:6pt;">{esc(pom['notes'])}</p>
  {ftr(style, 7, pages)}
</section>

<!-- PAGE 8 COLORWAY / LABELS / PACKING -->
<section class="page">
  {hdr(style, 'Colorway, labels and packing')}
  <h3>COLORWAY  ·  MID GREY</h3>
  <div class="swatch-row">
    <div class="swatch" style="background:{hexcol};"></div>
    <div class="swatch-info">
      <p><b>Sampled from Model 6 grey-set photographs (front hi frame, pant area).</b> Hex {hexcol}. Nearest Pantone TCX (approximate, not a certified match): {esc(pantone)}. <span class="badge">EST.</span></p>
      <p class="muted">Supplier to submit a lab dip on the approved chino twill, lit D65 / TL84 / incandescent, against this swatch and the photo reference. Do not approve production on the photograph alone. A second colorway is not specified in this proto pack.</p>
    </div>
  </div>
  <h3>LABELS</h3>
  <div class="lbl-grid">
    <b>Brand label</b><span>Woven, 1.1 × 0.5 in, folded, set at the center-back waistband, ¼ in below the top edge. “Atelier 360” or the brand mark TBD. <span class="badge">EST.</span></span>
    <b>Care / content</b><span>Printed satin or polyester taffeta, sewn into the left waistband facing (wearer’s left). Content as approved (e.g. 100% cotton, or 98% cotton 2% elastane if stretch is used). Care: machine wash cold, gentle; tumble low or line dry; warm iron; do not bleach. Country of origin TBD.</span>
    <b>Hangtag</b><span>Recycled board, one color, with style {esc(style)}, colorway Mid Grey, waist size, inseam / outseam, barcode placeholder. Attached at the right belt loop with a cotton string or Kimble.</span>
    <b>Size</b><span>Printed on the care label and on the hangtag as “W{inch(pom['base_waist'])} / {inch(pom['rows'][7]['base'])} inseam” (base), or the size actually cut.</span>
  </div>
  <h3>PACKING</h3>
  <p>Fold through the center back, waistband up, with a size sticker on the polybag (style, colorway, waist, inseam, outseam, PO / season SS27). No tissue required unless the fabric marks. 6–8 pieces per inner carton as the volume allows; outer carton marked with style, color, size run and quantity. <span class="badge">EST.</span></p>
  <h3>FIT NOTES FOR THE PROTO</h3>
  <p>Fit on the test profile / Model 6: 5 ft 6 in, 130 lb, body waist 30 in, hip {inch(v.get('hip'))} in. The 31 in garment waist should sit at the natural waist with about 1 in of ease, buttoned, hook closed, no gapping at the CB. The 35 in outseam is an ankle length — confirm the hem against the fit model’s shoe (barefoot reference in the photographs is about 4 in above the floor). Slim through the thigh and knee, no pulling at the seat or the fly. If the full-length chino is preferred later, extend inseam and outseam together; do not change the given 35 in outseam on this proto without a written revision.</p>
  {ftr(style, 8, pages)}
</section>

<!-- PAGE 9 SIGN-OFF -->
<section class="page">
  {hdr(style, 'Sign-off')}
  <p>First proto to be cut in US waist {inch(pom['base_waist'])}, outseam {inch(pom['base_outseam'])} in, colorway Mid Grey only. No graded set until the proto is approved. Return the proto with this pack, a measurement report against page 7, and a comment sheet. <span class="badge">EST.</span> items must be confirmed or corrected in writing.</p>
  <h3>REVISION</h3>
  <table style="margin-bottom:10pt;">
    <tr><th>Rev</th><th>Date</th><th class="l">Description</th><th class="l">By</th></tr>
    <tr><td class="c">00</td><td class="c">23 Nov 2026</td><td class="l">First issue. Test profile (5 ft 6 in, 130 lb; given waist 31 in, outseam 35 in). Fit model Model 6. All ungiven values estimated.</td><td class="l">Jordan Salazar</td></tr>
    <tr><td class="c">&nbsp;</td><td></td><td></td><td></td></tr>
    <tr><td class="c">&nbsp;</td><td></td><td></td><td></td></tr>
  </table>
  <h3>APPROVALS</h3>
  <div class="sign">
    <div class="box"><div class="role">DESIGNER</div><div class="line">Jordan Salazar</div><div class="line">Date</div></div>
    <div class="box"><div class="role">TECHNICAL DESIGN / PATTERN</div><div class="line">Name</div><div class="line">Date</div></div>
    <div class="box"><div class="role">MERCHANDISING / PRODUCTION</div><div class="line">Name</div><div class="line">Date</div></div>
    <div class="box"><div class="role">SUPPLIER  ·  PROTO RECEIVED</div><div class="line">Name / factory</div><div class="line">Date</div></div>
    <div class="box"><div class="role">FIT SESSION  ·  PROTO 1</div><div class="line">Result (approved / comments)</div><div class="line">Date</div></div>
    <div class="box"><div class="role">COLOR / LAB DIP</div><div class="line">Result</div><div class="line">Date</div></div>
  </div>
  <div class="disclaimer" style="margin-top:14pt;"><b>STATUS: FOR PROTO ONLY.</b> This document is a design and measurement brief for a first sample. It is not a production purchase order. Photograph references, estimated POMs, proposed materials and the approximate Pantone name must be confirmed before any bulk order. The measurement profile used to drive this pack is the test fixture “{esc(name)}”, saved in the Avata measure-screen JSON format.</div>
  {ftr(style, 9, pages, 'For proto only — confirm all EST. items before bulk')}
</section>

</body>
</html>
'''
    return html


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def find_fonts():
    candidates = [
        SHARED / 'techpacks' / '_build',
        Path('/usr/share/fonts/truetype/liberation'),
        Path('/usr/share/fonts/truetype/liberation2'),
    ]
    needed = [
        'LiberationSans-Regular.ttf', 'LiberationSans-Bold.ttf',
        'LiberationSans-Italic.ttf', 'LiberationSans-BoldItalic.ttf',
        'LiberationSerif-Regular.ttf', 'LiberationSerif-Bold.ttf',
    ]
    found = {}
    for n in needed:
        for root in candidates:
            p = root / n
            if p.is_file():
                found[n] = p
                break
        if n not in found:
            raise SystemExit(f'Missing font {n}')
    return found


def print_pdf(html_path: Path, pdf_path: Path):
    if not CHROME:
        raise SystemExit('google-chrome is required to print the PDF')
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
        '--no-pdf-header-footer', f'--print-to-pdf={pdf_path}',
        f'file://{html_path}',
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not pdf_path.is_file():
        raise SystemExit(f'Chrome failed to print the PDF:\n{r.stderr or r.stdout}')
    return pdf_path


def make_previews(pdf: Path, dest_dir: Path, names):
    if not PDFTOPPM:
        print('pdftoppm not found; skipping previews', file=sys.stderr)
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = dest_dir / 'page'
    subprocess.check_call([PDFTOPPM, '-png', '-r', '120', str(pdf), str(stem)])
    # pdftoppm writes page-1.png, page-2.png, ...
    written = []
    for i, label in enumerate(names, 1):
        src = dest_dir / f'page-{i}.png'
        if not src.is_file():
            src = dest_dir / f'page-{i:02d}.png'
        if src.is_file():
            dest = dest_dir / f'page-{i:02d}-{label}.png'
            if src.resolve() != dest.resolve():
                shutil.copy(src, dest)
            written.append(dest)
    return written


def run(args):
    prof = load_profile(args.profile)
    garment = (args.garment or 'chino').lower().replace('_', '-').replace(' ', '')
    if garment not in {'chino', 'pant', 'pants', '5-pocket', '5pocket', 'slimchino', 'chino-pant'}:
        raise SystemExit(f'Unsupported garment type {args.garment!r}. Use chino (or pant / 5-pocket).')
    style = args.style or 'AVA-002'
    model_id = args.model or prof.get('modelId') or 'exact-28'
    assets = Path(args.assets) if args.assets else (REPO / 'assets')
    out_pdf = Path(args.out)
    work = Path(args.build_dir) if args.build_dir else out_pdf.parent / '_build' / out_pdf.stem
    if work.exists() and args.clean:
        shutil.rmtree(work)
    img_dir = work / 'img'
    work.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(exist_ok=True)

    for name, src in find_fonts().items():
        dest = work / name
        if not dest.exists():
            shutil.copy(src, dest)

    frames = prep_frames(assets, model_id, img_dir)
    # sample colour from the front
    front = Image.open(frames[0]) if Image else None
    rgb = sample_garment_color(front) if front else (156, 152, 151)
    pantone = nearest_pantone(rgb)
    pantone_swatch(rgb, img_dir / 'swatch.png')

    # 8 views already in img_dir as 000.jpg ...
    imgs = {f'view-{a:03d}': f'img/{a:03d}.jpg' for a in frames}

    # detail crops from subject bbox (front / side / back)
    def subj(angle):
        im = Image.open(frames[angle])
        return im.size, find_subject(im)

    (w, h), (x0, y0, x1, y1) = subj(0)
    bh = y1 - y0
    # waist ~ 0.40 of body, crotch ~ 0.55, hem ~ 0.94
    crops = {
        'detail-waist-front': (frames[0], (x0 - 10, y0 + int(bh * 0.34), x1 + 10, y0 + int(bh * 0.58))),
        'detail-hip':         (frames[0], (x0 - 10, y0 + int(bh * 0.48), x1 + 10, y0 + int(bh * 0.72))),
        'detail-hem-front':   (frames[0], (x0 - 20, y0 + int(bh * 0.82), x1 + 20, y1 + 8)),
        'detail-side':        (frames[90], None),
        'detail-back-waist':  (frames[180], None),
        'detail-hem-back':    (frames[180], None),
    }
    _, sbox = subj(90)
    sx0, sy0, sx1, sy1 = sbox
    sh = sy1 - sy0
    crops['detail-side'] = (frames[90], (sx0 - 20, sy0 + int(sh * 0.32), sx1 + 20, sy1 + 4))
    _, bbox180 = subj(180)
    bx0, by0, bx1, by1 = bbox180
    bbh = by1 - by0
    crops['detail-back-waist'] = (frames[180], (bx0 - 10, by0 + int(bbh * 0.34), bx1 + 10, by0 + int(bbh * 0.62)))
    crops['detail-hem-back'] = (frames[180], (bx0 - 20, by0 + int(bbh * 0.82), bx1 + 20, by1 + 8))

    for key, (src, box) in crops.items():
        dest = img_dir / f'{key}.jpg'
        crop_jpeg(src, box, dest)
        imgs[key] = f'img/{key}.jpg'

    flats = work / 'flats.svg'
    flats.write_text(chino_flats_svg())
    # rasterize flats via chrome? SVG in img tag with file:// often works in Chrome print.
    imgs['flats'] = 'flats.svg'

    pom = chino_pom(prof)
    ctx = {
        'profile': prof,
        'pom': pom,
        'style': style,
        'rgb': rgb,
        'pantone': pantone,
        'imgs': imgs,
        'pages': 9,
    }
    html = build_html(ctx)
    html_path = work / 'techpack.html'
    html_path.write_text(html)
    print(f'Wrote {html_path}')
    print_pdf(html_path, out_pdf)
    print(f'Wrote {out_pdf} ({out_pdf.stat().st_size} bytes)')

    preview_names = ['cover', 'references', 'details', 'flats', 'bom', 'construction', 'pom', 'colorway', 'signoff']
    if args.previews:
        prevs = make_previews(out_pdf, Path(args.previews), preview_names)
        for pth in prevs:
            print(f'Preview {pth}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Generate a supplier tech-pack PDF from an Avata measurement profile.')
    ap.add_argument('--profile', required=True, help='Path to an avata-measure JSON export')
    ap.add_argument('--garment', default='chino', help='Garment type: chino | pant | 5-pocket')
    ap.add_argument('--out', required=True, help='Output PDF path')
    ap.add_argument('--previews', default='', help='Directory for PNG page previews (optional)')
    ap.add_argument('--assets', default='', help='Gallery assets root (default: <repo>/assets)')
    ap.add_argument('--model', default='', help='Fit-model id (default: profile modelId or exact-28)')
    ap.add_argument('--style', default='AVA-002', help='Style number (default AVA-002)')
    ap.add_argument('--build-dir', default='', help='Working directory for HTML/images')
    ap.add_argument('--clean', action='store_true', help='Clear the build directory first')
    args = ap.parse_args(argv)
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
