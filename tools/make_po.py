#!/usr/bin/env python3
"""Build a draft purchase-order enquiry PDF from a style, color, and size quantities.

This is an enquiry document, not a paid purchase order. It never sends email
or charges a card.

Example (from the model-gallery repo root):

    python3 tools/make_po.py \\
      --profile data/profiles/jordan-default.json \\
      --style AVA-002 \\
      --color "Mid Grey" \\
      --qty W30=20,W31=40,W32=40,W33=20 \\
      --ship 2027-03-15 \\
      --fit-sample \\
      --out /workspace/shared/model-gallery/orders/ava-002-sample-po.pdf \\
      --previews /workspace/shared/model-gallery/orders/previews/ava-002-sample-po \\
      --email-out /workspace/shared/model-gallery/orders/ava-002-sample-po-email.txt
"""
from __future__ import annotations

import argparse, csv, json, shutil, subprocess, sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SHARED = Path('/workspace/shared/model-gallery')
CHROME = shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium')
PDFTOPPM = shutil.which('pdftoppm')

MONTHS = ['January','February','March','April','May','June','July','August',
          'September','October','November','December']


def esc(s):
    return (str(s) if s is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def pretty_date(iso: str | None, fallback='To be confirmed'):
    if not iso:
        return fallback
    try:
        y, m, d = (int(x) for x in iso.split('-')[:3])
        return f'{d} {MONTHS[m-1]} {y}'
    except Exception:
        return iso


def load_styles(path: Path | None):
    p = path or (REPO / 'data' / 'styles.json')
    if p.is_file():
        data = json.loads(p.read_text())
        return data.get('styles') or []
    return []


def load_profile(path: Path | None):
    if not path:
        return None
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and data.get('profiles'):
        pid = data.get('activeId')
        return next((x for x in data['profiles'] if x.get('id') == pid), data['profiles'][0])
    return data if isinstance(data, dict) else None


def parse_qty(spec: str, style: dict) -> dict:
    """Parse W30=20,W31=40 or 30:20,31:40 into {display_size: qty}."""
    prefix = style.get('sizePrefix') or ''
    allowed = {str(s) for s in style.get('sizes') or []}
    out = {}
    if not spec:
        return out
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '=' in part:
            k, v = part.split('=', 1)
        elif ':' in part:
            k, v = part.split(':', 1)
        else:
            raise SystemExit(f'Bad qty token {part!r}. Use W30=20 or 30:20.')
        k = k.strip()
        raw = k[len(prefix):] if prefix and k.upper().startswith(prefix.upper()) else k
        raw = raw.lstrip('Ww') if prefix == 'W' and raw[:1] in 'Ww' else raw
        if allowed and raw not in allowed and k not in {prefix + s for s in allowed}:
            # still accept, but warn
            print(f'Note: size {k} is not in the style size list {sorted(allowed)}', file=sys.stderr)
        try:
            n = int(v.strip())
        except ValueError:
            raise SystemExit(f'Quantity for {k} is not an integer: {v}')
        if n < 0:
            raise SystemExit(f'Quantity for {k} cannot be negative')
        if n:
            out[f'{prefix}{raw}'] = n
    return out


def size_key(style, sz):
    return f"{style.get('sizePrefix') or ''}{sz}"


def find_fonts():
    candidates = [
        SHARED / 'techpacks' / '_build',
        Path('/usr/share/fonts/truetype/liberation'),
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


def email_draft(style, color, qtys, ship, notes, po_number, fit_sample, today):
    lines = [f'  {k}  —  {n}' for k, n in qtys.items()] or ['  (no bulk quantities entered)']
    bulk = sum(qtys.values())
    sample = ''
    if fit_sample:
        base = size_key(style, style.get('baseSize') or '')
        sample = f'\nPlease also cut one fit sample in the base size ({base}) of this pattern, per supplier, before the bulk cut.\n'
    note_line = f'Notes: {notes.strip()}\n' if (notes or '').strip() else ''
    return (
        f'Subject: Purchase order enquiry — {style["id"]} {style["name"]} — Atelier 360\n'
        '\n'
        'Hello,\n'
        '\n'
        f'Please find a purchase-order enquiry from Atelier 360 for style {style["id"]}, {style["name"]}, '
        f'colorway {color}, referencing the {style.get("techpack") or style["id"] + " technical package"}.\n'
        '\n'
        f'Draft PO number: {po_number}\n'
        f'Season: {style.get("season") or "SS27 Prototype"}\n'
        f'Quantities ({style.get("sizeLabel") or "size"}):\n'
        + '\n'.join(lines) + '\n'
        f'Bulk units: {bulk}\n'
        f'{sample}\n'
        f'Target ship date: {pretty_date(ship)}\n'
        f'{note_line}\n'
        'This is a draft enquiry for pricing, lead time and confirmation. It is not a paid purchase order '
        'and not an authorization to cut a bulk production run or to charge a card. Please confirm unit price, '
        'lead time, and proto / fit-sample availability against the technical package.\n'
        '\n'
        'Thank you,\n'
        'Jordan Salazar\n'
        'Atelier 360\n'
    )


def po_html(style, color, qtys, ship, notes, po_number, fit_sample, today, profile):
    sizes = style.get('sizes') or []
    prefix = style.get('sizePrefix') or ''
    # include any qty keys not in the official list (e.g. W33 if listed — it is)
    extra = [k[len(prefix):] if prefix and k.startswith(prefix) else k for k in qtys if (k[len(prefix):] if prefix and k.startswith(prefix) else k) not in {str(s) for s in sizes}]
    all_sizes = list(sizes) + extra
    rows = []
    for sz in all_sizes:
        k = size_key(style, sz)
        q = int(qtys.get(k, 0) or 0)
        base = str(sz) == str(style.get('baseSize'))
        cls = ' class="base"' if base else ''
        tag = ' <span class="muted">(base)</span>' if base else ''
        rows.append(f'<tr{cls}><td>{esc(k)}{tag}</td><td class="r">{q if q else "—"}</td></tr>')
    bulk = sum(int(v) for v in qtys.values())
    sample_row = ''
    total = bulk
    if fit_sample:
        basek = size_key(style, style.get('baseSize'))
        sample_row = f'<tr><td>Fit sample, base size {esc(basek)} (one per supplier, before bulk)</td><td class="r">1</td></tr>'
        total = bulk + 1
    fit = style.get('fitModel') or ''
    if profile and profile.get('name'):
        v = profile.get('values') or {}
        bits = [str(profile.get('name'))]
        ht = v.get('height')
        if ht:
            bits.append(f"{int(ht)//12} ft {int(ht)%12} in")
        wt = v.get('weight')
        if wt:
            bits.append(f"{int(wt)} lb")
        prefix = ', '.join(bits)
        fit = f"{prefix}. {fit}" if fit else prefix
    basek = size_key(style, style.get('baseSize'))
    # Don't append "Base W31." a second time when the style already names the base size.
    if fit and basek and basek.lower() not in fit.lower() and f"base size {basek}".lower() not in fit.lower():
        fit = (fit + '. ' if fit and not fit.endswith('.') else fit + ' ' if fit else '') + f'Base {basek}.'
    notes_html = f'<h2>NOTES</h2><p>{esc(notes)}</p>' if (notes or '').strip() else ''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{esc(po_number)} — Draft PO enquiry</title>
<style>
@font-face{{font-family:Sans;src:url("LiberationSans-Regular.ttf");font-weight:400;}}
@font-face{{font-family:Sans;src:url("LiberationSans-Bold.ttf");font-weight:700;}}
@font-face{{font-family:Serif;src:url("LiberationSerif-Regular.ttf");font-weight:400;}}
@font-face{{font-family:Serif;src:url("LiberationSerif-Bold.ttf");font-weight:700;}}
:root{{--ink:#161616;--muted:#5c5c57;--rule:#d0cec8;--est:#7a3f0c;--wash:#f3f2ee;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
@page{{size:letter;margin:0;}}
html,body{{background:#fff;color:var(--ink);font-family:Sans,Helvetica,Arial,sans-serif;font-size:10pt;line-height:1.4;}}
.page{{width:8.5in;height:11in;padding:0.5in 0.55in 0.45in;position:relative;overflow:hidden;background:#fff;}}
h1{{font-family:Serif,Georgia,serif;font-weight:700;font-size:24pt;line-height:1.05;margin:0 0 4pt;}}
h2{{font-size:10pt;letter-spacing:.1em;font-weight:700;border-bottom:1.2pt solid var(--ink);padding-bottom:3pt;margin:16pt 0 8pt;}}
.kicker{{letter-spacing:.16em;font-size:8.5pt;font-weight:700;color:var(--est);}}
.top{{display:flex;justify-content:space-between;gap:16pt;border-bottom:2pt solid var(--ink);padding-bottom:10pt;margin-bottom:14pt;}}
.brand{{font-weight:700;letter-spacing:.2em;font-size:10pt;}}
.muted{{color:var(--muted);}}
table{{width:100%;border-collapse:collapse;font-size:9.5pt;margin:6pt 0 10pt;}}
th,td{{border:0.45pt solid #c8c6c0;padding:5pt 8pt;text-align:left;vertical-align:top;}}
th{{background:var(--wash);letter-spacing:.04em;font-size:8pt;}}
td.r,th.r{{text-align:right;white-space:nowrap;}}
tr.base td{{background:#ebeae5;font-weight:700;}}
.meta th,.meta td{{border:none;border-bottom:0.4pt solid var(--rule);background:none;padding:4.5pt 8pt 4.5pt 0;}}
.meta th{{width:1.7in;color:var(--muted);letter-spacing:.08em;font-size:7.5pt;text-transform:uppercase;font-weight:700;}}
.disclaimer{{margin-top:16pt;border:0.8pt solid var(--est);color:var(--est);padding:8pt 10pt;font-size:8.5pt;line-height:1.4;}}
footer{{position:absolute;left:0.55in;right:0.55in;bottom:0.28in;border-top:0.5pt solid var(--rule);padding-top:4pt;display:flex;justify-content:space-between;font-size:7.5pt;color:var(--muted);}}
</style>
</head>
<body>
<section class="page">
  <div class="top">
    <div>
      <div class="brand">ATELIER 360</div>
      <div class="muted" style="font-size:8pt;margin-top:2pt;letter-spacing:.08em;">APPAREL  ·  PURCHASE ORDER ENQUIRY</div>
    </div>
    <div style="text-align:right;">
      <div class="kicker">DRAFT  ·  NOT A PAID ORDER</div>
      <div style="font-weight:700;font-size:14pt;margin-top:3pt;">{esc(po_number)}</div>
      <div class="muted" style="font-size:9pt;">{esc(pretty_date(today))}</div>
    </div>
  </div>
  <h1>{esc(style['name'])}</h1>
  <p class="muted">{esc(style['id'])}  ·  {esc(style.get('season') or 'SS27 Prototype')}  ·  Colorway {esc(color)}</p>
  <table class="meta">
    <tr><th>Supplier</th><td>To be confirmed</td></tr>
    <tr><th>Tech pack</th><td>{esc(style.get('techpack') or style['id'] + ' technical package')}</td></tr>
    <tr><th>Fit / base size</th><td>{esc(fit)}</td></tr>
    <tr><th>Target ship date</th><td>{esc(pretty_date(ship))}</td></tr>
    <tr><th>Buyer</th><td>Jordan Salazar, Atelier 360</td></tr>
  </table>
  <h2>QUANTITIES  ·  {esc(style.get('sizeLabel') or 'Size')}</h2>
  <table>
    <tr><th>Size</th><th class="r">Units</th></tr>
    {''.join(rows)}
    <tr><td>Bulk total</td><td class="r">{bulk}</td></tr>
    {sample_row}
    <tr class="base"><td>Total units to discuss</td><td class="r">{total}</td></tr>
  </table>
  {notes_html}
  <div class="disclaimer"><b>DRAFT ENQUIRY ONLY.</b> This document is for pricing, lead time and confirmation against the referenced technical package. It is not a paid purchase order, not a contract, and not an authorization to cut a bulk production run or to charge a card. Confirm unit price, lead time and proto / fit-sample availability in writing before any cut. One fit sample per base pattern per supplier is recommended before a bulk cut.</div>
  <footer><span>Atelier 360  ·  Confidential</span><span>Draft enquiry — nothing has been sent or charged</span><span>01 / 01</span></footer>
</section>
</body>
</html>
'''


def print_pdf(html_path: Path, pdf_path: Path):
    if not CHROME:
        raise SystemExit('google-chrome is required to print the PDF')
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--no-pdf-header-footer', f'--print-to-pdf={pdf_path}', f'file://{html_path}']
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not pdf_path.is_file():
        raise SystemExit(f'Chrome failed to print the PDF:\n{r.stderr or r.stdout}')
    return pdf_path


def make_previews(pdf: Path, dest_dir: Path, names=('cover',)):
    if not PDFTOPPM:
        print('pdftoppm not found; skipping previews', file=sys.stderr)
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = dest_dir / 'page'
    subprocess.check_call([PDFTOPPM, '-png', '-r', '120', str(pdf), str(stem)])
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


def write_csv(path: Path, style, color, qtys, ship, notes, po_number, fit_sample):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['po_number','style','style_name','color','size','qty','kind','ship_date','fit_sample','notes','status'])
        note = ' '.join((notes or '').split())
        for k, n in qtys.items():
            w.writerow([po_number, style['id'], style['name'], color, k, n, 'bulk', ship or '', 'yes' if fit_sample else 'no', note, 'DRAFT enquiry'])
        if fit_sample:
            w.writerow([po_number, style['id'], style['name'], color, size_key(style, style.get('baseSize')), 1, 'fit-sample', ship or '', 'yes', note, 'DRAFT enquiry'])


def main(argv=None):
    ap = argparse.ArgumentParser(description='Generate a draft purchase-order enquiry PDF (never sends or charges).')
    ap.add_argument('--profile', default='', help='Optional avata-measure JSON, for the fit-model line')
    ap.add_argument('--garment', default='', help='Ignored if --style is set; chino maps to AVA-002, tank to AVA-001')
    ap.add_argument('--style', default='', help='Style id, e.g. AVA-002')
    ap.add_argument('--color', default='', help='Colorway (default is the style default)')
    ap.add_argument('--qty', required=True, help='Size quantities, e.g. W30=20,W31=40,W32=40,W33=20')
    ap.add_argument('--ship', default='', help='Target ship date YYYY-MM-DD')
    ap.add_argument('--notes', default='', help='Notes on the PO')
    ap.add_argument('--fit-sample', dest='fit_sample', action='store_true', help='Include one fit sample in the base size')
    ap.add_argument('--no-fit-sample', dest='fit_sample', action='store_false')
    ap.set_defaults(fit_sample=True)
    ap.add_argument('--po-number', default='', help='Draft PO number')
    ap.add_argument('--styles', default='', help='Path to data/styles.json')
    ap.add_argument('--out', required=True, help='Output PDF path')
    ap.add_argument('--previews', default='', help='Directory for PNG page previews')
    ap.add_argument('--csv-out', default='', help='Optional CSV path')
    ap.add_argument('--email-out', default='', help='Optional path for the email-draft text')
    ap.add_argument('--build-dir', default='')
    args = ap.parse_args(argv)

    styles = load_styles(Path(args.styles) if args.styles else None)
    if not styles:
        raise SystemExit('No styles catalog found (data/styles.json).')
    sid = args.style
    if not sid:
        g = (args.garment or '').lower()
        if g in {'chino', 'pant', 'pants', '5-pocket', '5pocket'}:
            sid = 'AVA-002'
        elif g in {'tank', 'shorts', 'set', 'tank-shorts', 'ava-001'}:
            sid = 'AVA-001'
        else:
            sid = 'AVA-002'
    style = next((s for s in styles if s['id'] == sid), None)
    if not style:
        raise SystemExit(f'Unknown style {sid}. Known: {", ".join(s["id"] for s in styles)}')
    color = args.color or style.get('defaultColor') or ((style.get('colors') or [''])[0])
    qtys = parse_qty(args.qty, style)
    if not qtys and not args.fit_sample:
        raise SystemExit('Enter at least one quantity, or pass --fit-sample.')
    today = date.today().isoformat()
    po_number = args.po_number or f"AVA-PO-{today.replace('-', '')}-001"
    profile = load_profile(Path(args.profile)) if args.profile else None
    notes = args.notes
    ship = args.ship

    out_pdf = Path(args.out)
    work = Path(args.build_dir) if args.build_dir else out_pdf.parent / '_build' / out_pdf.stem
    work.mkdir(parents=True, exist_ok=True)
    for name, src in find_fonts().items():
        dest = work / name
        if not dest.exists():
            shutil.copy(src, dest)

    html = po_html(style, color, qtys, ship, notes, po_number, args.fit_sample, today, profile)
    html_path = work / 'po.html'
    html_path.write_text(html)
    print_pdf(html_path, out_pdf)
    print(f'Wrote {out_pdf} ({out_pdf.stat().st_size} bytes)')

    if args.previews:
        for pth in make_previews(out_pdf, Path(args.previews)):
            print(f'Preview {pth}')
    csv_path = Path(args.csv_out) if args.csv_out else out_pdf.with_suffix('.csv')
    write_csv(csv_path, style, color, qtys, ship, notes, po_number, args.fit_sample)
    print(f'Wrote {csv_path}')
    draft = email_draft(style, color, qtys, ship, notes, po_number, args.fit_sample, today)
    email_path = Path(args.email_out) if args.email_out else out_pdf.with_name(out_pdf.stem + '-email.txt')
    email_path.write_text(draft)
    print(f'Wrote {email_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
