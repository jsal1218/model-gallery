#!/usr/bin/env python3
"""Supplier tech packs for gallery outfits (Model 1 and later).

Imported by tools/make_techpack.py. Builds a US-Letter PDF from a fit-model
profile plus the outfit's real 360 frames. Every POM, fabric and construction
call is an estimate unless a value is explicitly marked given. Colors are
approximate photo samples, not lab dips.
"""
from __future__ import annotations

import json, shutil, subprocess, sys, zipfile
from datetime import date
from pathlib import Path

# make_techpack.py lives in the same folder and is on sys.path when dispatched.
import make_techpack as mt

REPO = mt.REPO
SHARED = mt.SHARED
SIZES = ['XS', 'S', 'M', 'L', 'XL']
SIZE_STEP = {'XS': -2, 'S': -1, 'M': 0, 'L': 1, 'XL': 2}
# circumference grade (full body, inches per size step); lengths use LEN_STEP
CIRC_STEP = 2.0
WAIST_STEP = 1.5
LEN_STEP = 0.375
STRAP_STEP = 0.0
TODAY = '23 November 2026'
DESIGNER = 'Jordan Salazar'
SEASON = 'SS27 Prototype'

# Approximate TCX references used only as a starting point from photographs.
PANTONE_NEAR = [
    ((255, 255, 255), '11-0601 TCX Bright White'),
    ((242, 236, 230), '11-0602 TCX Snow White'),
    ((232, 224, 218), '12-0304 TCX Turtledove'),
    ((222, 213, 209), '13-0905 TCX White Swan'),
    ((233, 191, 192), '14-1513 TCX Prism Pink'),
    ((242, 224, 223), '13-1404 TCX Pearl Blush'),
    ((236, 178, 176), '16-1620 TCX Coral Pink'),
    ((193, 192, 197), '14-4102 TCX Micro Chip'),
    ((185, 185, 187), '14-4201 TCX Lunar Rock'),
    ((181, 177, 174), '15-4502 TCX Silver Cloud'),
    ((176, 171, 168), '16-3801 TCX Wind Chime'),
    ((154, 153, 160), '16-3905 TCX Glacier Gray'),
    ((78, 59, 54), '19-1111 TCX Chocolate Torte'),
    ((80, 60, 53), '19-1116 TCX Dark Earth'),
    ((72, 64, 57), '19-0912 TCX Black Olive'),
    ((67, 57, 51), '19-0809 TCX Chocolate Brown'),
    ((154, 169, 187), '16-4019 TCX Chambray Blue'),
    ((126, 129, 130), '17-4402 TCX Storm Gray'),
    ((120, 114, 109), '18-3907 TCX Charcoal Gray'),
    ((60, 55, 59), '19-3908 TCX Jet Black'),
    ((51, 52, 58), '19-3906 TCX Black Beauty'),
    ((30, 30, 30), '19-3911 TCX Black Beauty'),
    ((36, 36, 34), '19-0303 TCX Jet Black'),
    ((27, 25, 26), '19-4005 TCX Black'),
    ((46, 41, 43), '19-4007 TCX Stretch Limo'),
    ((155, 27, 48), '18-1664 TCX Racing Red'),
    ((25, 39, 72), '19-3921 TCX Navy Blazer'),
    ((190, 184, 179), '14-4103 TCX Cloud Gray'),
]


def nearest_pantone(rgb):
    best, bd = PANTONE_NEAR[0], 1e9
    r, g, b = rgb
    for c, name in PANTONE_NEAR:
        d = (r - c[0]) ** 2 + (g - c[1]) ** 2 + (b - c[2]) ** 2
        if d < bd:
            best, bd = (c, name), d
    return best[1]


def esc(s):
    return mt.esc(s)


def inch(v):
    return mt.inch(v)


def grade(base, kind, sz):
    step = SIZE_STEP[sz]
    if kind in ('hold', 'fixed'):
        return float(base)
    if kind == 'circ':
        return float(base) + CIRC_STEP * step
    if kind in ('waist', 'waist_stretch'):
        return float(base) + WAIST_STEP * step
    if kind in ('len', 'length'):
        return float(base) + LEN_STEP * step
    if kind == 'sleeve':
        return float(base) + 0.25 * step
    if kind == 'strap':
        return float(base) + STRAP_STEP * step
    if kind == 'small':
        return float(base) + 0.25 * step
    if kind == 'mid':
        return float(base) + 0.75 * step
    return float(base) + CIRC_STEP * step


def pom(code, name, how, base, g='circ'):
    return {'code': code, 'name': name, 'how': how, 'base': base, 'grade': g}


def piece(pid, name, kind, fabric, construction, poms, color_name, color_box,
          bom=None, notes=''):
    return {
        'id': pid, 'name': name, 'kind': kind, 'fabric': fabric,
        'construction': construction, 'poms': poms, 'color_name': color_name,
        'color_box': color_box, 'bom': bom or [], 'notes': notes,
    }


def style(**kw):
    kw.setdefault('season', SEASON)
    kw.setdefault('sizes', list(SIZES))
    kw.setdefault('base_size', 'M')
    kw.setdefault('size_prefix', '')
    kw.setdefault('size_label', 'US size')
    kw.setdefault('units', 'in')
    kw.setdefault('accessories', '')
    kw.setdefault('caveats', [])
    kw.setdefault('fit_notes', '')
    return kw


# ---------------------------------------------------------------------------
# Model 1 catalog (exact-26). Style codes AVA-003 onward, in gallery outfit order.
# Outfit numbers in the name match the gallery (Outfit 1 … Outfit 12).
# Base is a real grey crop set, so it is included as AVA-003.
# ---------------------------------------------------------------------------

_F_STRETCH = (
    'Mid-weight stretch jersey or a nylon/elastane performance knit, ~200–240 g/m², '
    'with at least 15% stretch and clean recovery. {color} face as photographed. '
    'Supplier to confirm weight, stretch, recovery and shrinkage. EST.'
)
_F_RIB = 'Fine rib stretch knit, ~180–220 g/m², with recovery. {color}. EST.'
_F_DENIM = (
    'Cotton denim, ~10–12 oz/yd² (340–400 g/m²), {color} wash as photographed. '
    'Slight mechanical stretch optional (98/2 or 99/1 cotton-elastane). EST.'
)
_F_SWEAT = 'Cotton or cotton-blend fleece / french terry, ~280–320 g/m², {color}, brushed or loop back. EST.'
_F_SATIN = 'Acetate or polyester satin (or silk-look charmeuse), ~80–120 g/m², {color}, with a soft drape and a clean face. EST.'
_F_WOVEN_LT = 'Light woven (cotton poplin, rayon blend or similar), ~80–120 g/m², {color}. EST.'
_F_SUITING = 'Wool-blend or viscose suiting, ~220–280 g/m², {color}, with a dry hand and a slight drape. EST.'
_F_SHIRTING = 'Cotton or cotton-blend shirting, ~100–120 g/m², {color}, easy-care finish optional. EST.'
_F_LEATHER = (
    'Garment-weight leather or a leather alternative with a comparable hand, {color}, '
    'with contrast panels as photographed. If leather, 1.0–1.2 mm, chrome-free preferred. '
    'If an alternative, confirm abrasion, flex and colorfastness. EST.'
)
_F_JERSEY_KIT = 'Performance soccer jersey knit (polyester interlock or similar), ~140–160 g/m², moisture-wicking, {color}. EST.'
_F_HOODIE = 'Mid-weight stretch jersey or a light scuba/ponte, ~240–280 g/m², {color}, with enough body to hold a zip-through crop. EST.'

_C_STITCH = [
    'Seam allowance ⅜ in unless noted. Stitch 10–12 SPI lockstitch; merrow or 3-thread overlock on raw edges of knits. EST.',
    'Needle and thread to match face unless a contrast topstitch is called out. Bar-tack pocket corners and high-stress points. EST.',
    'Confirm first proto on the Model 1 fit profile (5 ft 6 in / 130 lb, size M) before a size set. EST.',
]


def _knit_crop_poms(bust=32.0, under=28.5, hem=28.0, cf=10.5, strap=0.75, neck=6.5):
    return [
        pom('A', 'Bust circumference', 'Around the fullest bust, garment laid flat × 2, relaxed.', bust, 'circ'),
        pom('B', 'Underbust / band', 'Around the underbust or bottom band, laid flat × 2, relaxed.', under, 'waist'),
        pom('C', 'Hem circumference', 'Around the hem, laid flat × 2, relaxed.', hem, 'circ'),
        pom('D', 'Center-front length', 'HPS or neckline CF to front hem, along the body.', cf, 'len'),
        pom('E', 'Center-back length', 'Nape or CB neckline to back hem.', cf + 0.25, 'len'),
        pom('F', 'Strap / shoulder width', 'Finished visible strap or shoulder strap width.', strap, 'strap'),
        pom('G', 'Neck opening (CF to CB, laid flat)', 'Half the neck opening, laid flat.', neck, 'small'),
    ]


def _short_poms(waist=26.0, hip=36.0, thigh=22.0, inseam=2.75, outseam=9.0, rise_f=9.0, rise_b=13.0, hem=20.0):
    return [
        pom('H', 'Waist circumference, relaxed', 'Around the waist, laid flat × 2, relaxed (unstretched).', waist, 'waist'),
        pom('I', 'Hip / seat circumference', 'Around the fullest seat, laid flat × 2.', hip, 'circ'),
        pom('J', 'Thigh circumference', '1 in below the crotch, laid flat × 2.', thigh, 'circ'),
        pom('K', 'Front rise', 'CF waist to crotch seam.', rise_f, 'len'),
        pom('L', 'Back rise', 'CB waist over the seat to the crotch seam.', rise_b, 'len'),
        pom('M', 'Inseam', 'Crotch seam to hem, along the inseam.', inseam, 'hold'),
        pom('N', 'Outseam', 'Side waist to hem.', outseam, 'len'),
        pom('O', 'Leg opening', 'Around the hem, laid flat × 2.', hem, 'circ'),
    ]


def _pant_poms(waist=28.0, hip=39.5, thigh=23.5, knee=16.5, hem=18.0, inseam=31.0, outseam=40.5, rise_f=10.5, rise_b=14.75):
    return [
        pom('H', 'Waist circumference', 'Around the waist, laid flat × 2, relaxed.', waist, 'waist'),
        pom('I', 'Hip / seat circumference', 'Around the fullest seat, laid flat × 2.', hip, 'circ'),
        pom('J', 'Thigh circumference', '1 in below the crotch, laid flat × 2.', thigh, 'circ'),
        pom('K', 'Knee circumference', 'At mid-knee, laid flat × 2.', knee, 'circ'),
        pom('L', 'Hem / leg opening', 'Around the hem, laid flat × 2.', hem, 'circ'),
        pom('M', 'Front rise', 'CF waist to crotch seam.', rise_f, 'len'),
        pom('N', 'Back rise', 'CB waist over the seat to the crotch seam.', rise_b, 'len'),
        pom('O', 'Inseam', 'Crotch seam to hem.', inseam, 'len'),
        pom('P', 'Outseam', 'Side waist to hem.', outseam, 'len'),
    ]


CATALOG = []


def _add(st):
    CATALOG.append(style(**st))


_add(dict(
    id='AVA-003', name='Grey Crop Set', outfit_id='base', outfit_label='Base',
    slug='base-grey-crop-set', kind='set',
    tagline='Racerback sports crop and fitted booty short',
    default_color='Mid Grey',
    colors=['Mid Grey'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Model 1 Base. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Barefoot in the reference photographs. No additional garments in this pack.',
    fit_notes='A close, compressive fit through the bust and seat. The short should cover the seat without cutting in at the leg. Size M is the first proto on this 5 ft 6 in / 130 lb fit model (bust 36 / waist 27 / hip 38.5, all EST.).',
    pieces=[
        piece('top', 'Racerback sports crop', 'crop-racer',
              _F_STRETCH.format(color='mid grey'),
              [
                  'Front: lined or self-lined bust with a wide underbust band, no visible hardware. EST.',
                  'Racerback with a scooped back neck; straps join into a single back panel. EST.',
                  'Clean-finish or folded hem, ⅜–½ in. EST.',
                  'Optional removable cups; default is a lined shelf, no pads, unless the supplier recommends otherwise. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.0, under=28.0, hem=28.0, cf=10.0, strap=1.25, neck=7.0),
              'Mid Grey', (0.38, 0.24, 0.62, 0.40),
              bom=[('Self fabric', '1', 'Mid-weight stretch knit, mid grey', 'Body, lining'),
                   ('Thread', 'as needed', 'Polyester, tone-on-tone', 'Seams, hems')]),
        piece('bottom', 'Fitted booty short', 'booty-short',
              _F_STRETCH.format(color='mid grey, to match the crop'),
              [
                  'Fitted short with a mid-to-high rise, cover-the-seat length, about a 2¾ in inseam. EST.',
                  'Elastic or fold-over waist, no exposed elastic on the face. EST.',
                  'Gusset of self or a breathable mesh, bound. EST.',
                  'Clean hem, ⅜ in. No side stripe. EST.',
              ] + _C_STITCH,
              _short_poms(waist=25.5, hip=35.5, thigh=21.5, inseam=2.75, outseam=8.75, rise_f=8.75, rise_b=13.0, hem=19.5),
              'Mid Grey', (0.38, 0.44, 0.62, 0.55),
              bom=[('Self fabric', '1', 'Same knit as the crop, mid grey', 'Body, gusset'),
                   ('Waist elastic', '1', 'Soft elastic, ¾–1 in, enclosed', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-004', name='Pink Zip Hoodie Crop & Flare Pant', outfit_id='outfit-1', outfit_label='Outfit 1',
    slug='outfit-1-pink-zip-hoodie-flare-pant', kind='set',
    tagline='Dusty-pink zip-through crop hoodie and mid-rise flare pant',
    default_color='Dusty Pink',
    colors=['Dusty Pink'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 1. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Silver low sneakers appear in the photographs as styling only and are not in this BOM.',
    fit_notes='The hoodie is a close, zip-through crop that ends above the navel. The pant is mid-rise, slim through the thigh, and flares from the knee, long enough to break over a low sneaker. First proto in size M.',
    pieces=[
        piece('top', 'Zip-through crop hoodie', 'crop-zip-hoodie',
              _F_HOODIE.format(color='dusty pink'),
              [
                  'Fitted long-sleeve crop with a grown-on or set-in hood and a CF separating zipper to the neck. EST.',
                  'Princess or contour seaming at the bust, as photographed. EST.',
                  'Thumbhole or extended cuff optional; default is a plain close cuff. EST.',
                  'Clean hem at the crop, ½ in. Hood sits close, no heavy drawcord. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=33.5, under=29.5, hem=29.0, cf=13.5, strap=0, neck=6.5) + [
                  pom('S', 'Sleeve length, from shoulder', 'Shoulder point to cuff, slightly bent.', 23.0, 'sleeve'),
                  pom('T', 'Bicep circumference', '1 in below the armhole, laid flat × 2.', 11.5, 'mid'),
              ],
              'Dusty Pink', (0.38, 0.26, 0.62, 0.40),
              bom=[('Self fabric', '1', 'Stretch jersey or light ponte, dusty pink', 'Body, hood, sleeves'),
                   ('Zipper', '1', 'Separating CF zip, ~12–14 in, tone-on-tone or silver', 'Center front'),
                   ('Thread', 'as needed', 'Polyester, tone-on-tone', 'Seams')]),
        piece('bottom', 'Mid-rise flare pant', 'flare-pant',
              _F_STRETCH.format(color='dusty pink, to match the hoodie'),
              [
                  'Mid-rise flare with a close thigh and a flare from just below the knee. EST.',
                  'Contour side seaming as photographed. Fold-over or elastic waist, no visible jean hardware. EST.',
                  'Outseam may take a ⅛ in topstitch. Hem ¾ in, clean. EST.',
              ] + _C_STITCH,
              _pant_poms(waist=27.0, hip=39.0, thigh=22.5, knee=15.5, hem=20.5, inseam=31.0, outseam=40.75, rise_f=10.25, rise_b=14.5),
              'Dusty Pink', (0.40, 0.50, 0.60, 0.72),
              bom=[('Self fabric', '1', 'Same family as the hoodie, dusty pink', 'Body'),
                   ('Waist elastic', '1', 'Soft elastic, enclosed', 'Waist')]),
    ],
))


_add(dict(
    id='AVA-005', name='Brown Halter Crop & Short', outfit_id='outfit-2', outfit_label='Outfit 2',
    slug='outfit-2-brown-halter-crop-short', kind='set',
    tagline='Chocolate zip halter crop and contrast-piped booty short',
    default_color='Chocolate Brown',
    colors=['Chocolate Brown'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 2. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='White crew socks and light sneakers are styling only and are not in this BOM.',
    fit_notes='Compressive crop with a CF zip and a halter neck; contrast binding as photographed. The short is a fitted booty length with light contrast piping and a V seam at the back. First proto in size M.',
    pieces=[
        piece('top', 'Zip halter crop', 'crop-halter-zip',
              _F_STRETCH.format(color='chocolate brown'),
              [
                  'Halter neck with a CF separating zipper through the bust. EST.',
                  'Contrast light binding or piping at the neck, armhole and underbust, as photographed. EST.',
                  'Lined bust; clean crop hem. Open back below the halter join. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.0, under=27.5, hem=27.5, cf=10.25, strap=1.0, neck=5.5),
              'Chocolate Brown', (0.38, 0.26, 0.62, 0.40),
              bom=[('Self fabric', '1', 'Stretch knit, chocolate brown', 'Body, lining'),
                   ('Contrast binding', 'as needed', 'Light taupe / bone stretch binding', 'Neck, armhole, seams'),
                   ('Zipper', '1', 'Separating CF zip, ~8–10 in, tone-on-tone', 'Center front')]),
        piece('bottom', 'Piped booty short', 'short-piped',
              _F_STRETCH.format(color='chocolate brown, to match the crop'),
              [
                  'Fitted booty short with light contrast piping at the side and leg, and a V-shaped back seam as photographed. EST.',
                  'Fold-over or elastic waist, gusseted. EST.',
              ] + _C_STITCH,
              _short_poms(waist=25.5, hip=35.5, thigh=21.5, inseam=2.5, outseam=8.5, rise_f=8.5, rise_b=12.75, hem=19.0),
              'Chocolate Brown', (0.38, 0.44, 0.62, 0.54),
              bom=[('Self fabric', '1', 'Same knit, chocolate brown', 'Body, gusset'),
                   ('Contrast piping', 'as needed', 'Light taupe / bone cord piping', 'Side and leg'),
                   ('Waist elastic', '1', 'Soft elastic, enclosed', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-006', name='Cream Long-Sleeve Crop & Cargo Jean', outfit_id='outfit-3', outfit_label='Outfit 3',
    slug='outfit-3-cream-ls-crop-cargo-jean', kind='set',
    tagline='Cream bound long-sleeve crop and dark cargo jean',
    default_color='Cream',
    colors=['Cream', 'Dark Brown Cargo'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 3. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Light sneakers are styling only and are not in this BOM.',
    fit_notes='The crop is a close long-sleeve with a square/sweetheart neck, a small self-tie at CF, contrast binding and a slightly fluted hem. The jean is a mid-rise wide/straight cargo in a dark brown wash, long enough to break over a sneaker. First proto in size M.',
    pieces=[
        piece('top', 'Bound long-sleeve crop', 'crop-ls-square',
              _F_RIB.format(color='cream / bone'),
              [
                  'Fitted long sleeve with a square-to-sweetheart neck and a small self-tie or bow at CF, as photographed. EST.',
                  'Contrast brown binding at the neck and a sleeve insert or binding at the upper arm. EST.',
                  'Slight lettuce or fluted hem at the crop. Set-in sleeve, close cuff. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=33.0, under=28.5, hem=29.0, cf=12.0, strap=0, neck=6.0) + [
                  pom('S', 'Sleeve length, from shoulder', 'Shoulder point to cuff.', 23.0, 'sleeve'),
                  pom('T', 'Bicep circumference', '1 in below the armhole, laid flat × 2.', 11.25, 'mid'),
              ],
              'Cream', (0.38, 0.26, 0.62, 0.40),
              bom=[('Self fabric', '1', 'Fine rib or stretch knit, cream', 'Body, sleeves'),
                   ('Contrast binding', 'as needed', 'Dark brown stretch binding', 'Neck, sleeve insert'),
                   ('Thread', 'as needed', 'Tone-on-tone and contrast as needed', 'Seams')]),
        piece('bottom', 'Dark cargo jean', 'cargo-jean',
              _F_DENIM.format(color='dark brown / black-olive wash'),
              [
                  'Mid-rise, wide-to-straight leg, full length. Zip fly and button, belt loops. EST.',
                  'Thigh cargo pockets with a flap, as photographed, plus back patch pockets. EST.',
                  'Clean or slightly faded wash; no heavy distressing. ⅜ in topstitch in a tone-close thread. EST.',
              ] + _C_STITCH,
              _pant_poms(waist=28.5, hip=40.0, thigh=24.0, knee=17.5, hem=18.5, inseam=31.0, outseam=41.0, rise_f=10.75, rise_b=15.0),
              'Dark Brown Cargo', (0.38, 0.52, 0.62, 0.78),
              bom=[('Denim', '1', '10–12 oz cotton denim, dark brown wash', 'Body, pockets'),
                   ('Pocketing', 'as needed', 'Light cotton pocketing', 'Pockets'),
                   ('Zip fly', '1', 'Metal or antique-brass jean zip', 'CF fly'),
                   ('Button / rivets', 'as needed', 'Antique brass, to match', 'Waist, pockets'),
                   ('Belt loops', '5–6', 'Self denim, ½ in', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-007', name='White Halter Top & Denim Cargo Jort', outfit_id='outfit-4', outfit_label='Outfit 4',
    slug='outfit-4-white-halter-cargo-jort', kind='set',
    tagline='Off-white tie-front halter and light-wash cargo jort',
    default_color='Off White',
    colors=['Off White', 'Light Wash Denim'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 4. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='White crew socks and light sneakers are styling only and are not in this BOM.',
    fit_notes='The halter is a close, tie-front crop with an open back and neck ties. The jort is a mid-rise, knee-ish cargo short in a light wash with a raw hem. First proto in size M.',
    pieces=[
        piece('top', 'Tie-front halter crop', 'crop-halter-tie',
              _F_WOVEN_LT.format(color='off-white / bone') + ' A light stretch woven or a stable knit is acceptable if the tie holds. EST.',
              [
                  'Halter neck with self-ties at the nape and a gathered or tie CF, as photographed. EST.',
                  'Open back; bust lined or self-lined. Crop hem, clean. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.5, under=27.5, hem=27.5, cf=9.5, strap=0.6, neck=5.0),
              'Off White', (0.42, 0.28, 0.58, 0.40),
              bom=[('Self fabric', '1', 'Light woven or stable knit, off-white', 'Body, ties, lining'),
                   ('Thread', 'as needed', 'Tone-on-tone', 'Seams')]),
        piece('bottom', 'Light-wash cargo jort', 'cargo-jort',
              _F_DENIM.format(color='light blue / chambray wash'),
              [
                  'Mid-rise denim jort, length just above the knee, raw or slightly frayed hem as photographed. EST.',
                  'Zip fly, button, belt loops, thigh cargo flaps, back pockets. EST.',
                  'Light wash, modest fading, no heavy rips. EST.',
              ] + _C_STITCH,
              _short_poms(waist=28.5, hip=40.0, thigh=24.5, inseam=8.5, outseam=19.0, rise_f=11.0, rise_b=15.25, hem=20.5),
              'Light Wash Denim', (0.36, 0.48, 0.64, 0.70),
              bom=[('Denim', '1', '10–12 oz cotton denim, light wash', 'Body, pockets'),
                   ('Pocketing', 'as needed', 'Light cotton pocketing', 'Pockets'),
                   ('Zip fly + button', '1 set', 'Antique brass or silver jean trim', 'CF, waist'),
                   ('Belt loops', '5–6', 'Self denim', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-008', name='Cream Cami Crop & Wide Sweatpant', outfit_id='outfit-5', outfit_label='Outfit 5',
    slug='outfit-5-cream-cami-wide-sweatpant', kind='set',
    tagline='Cream zip cami crop and heather-grey wide sweatpant',
    default_color='Cream',
    colors=['Cream', 'Heather Grey'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 5. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Light sneakers are styling only and are not in this BOM.',
    fit_notes='The cami is a close crop with skinny straps, a short CF zipper and a slightly fluted hem. The sweatpant is a relaxed wide leg with a drawcord waist, long enough to cover the shoe. First proto in size M.',
    pieces=[
        piece('top', 'Zip cami crop', 'crop-cami',
              _F_RIB.format(color='cream / bone'),
              [
                  'Fitted cami crop, skinny straps, short CF zipper, slightly fluted or lettuce hem as photographed. EST.',
                  'Lined bust optional. Clean-finish neck and armhole. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.5, under=28.0, hem=28.5, cf=10.5, strap=0.4, neck=6.5),
              'Cream', (0.40, 0.26, 0.60, 0.40),
              bom=[('Self fabric', '1', 'Fine rib or stretch knit, cream', 'Body'),
                   ('Zipper', '1', 'Short CF zip, ~6–8 in, tone-on-tone', 'Center front'),
                   ('Elastic / strap', 'as needed', 'Self or clear, if needed for strap', 'Straps')]),
        piece('bottom', 'Wide sweatpant', 'sweat-wide',
              _F_SWEAT.format(color='heather mid grey'),
              [
                  'Relaxed wide-leg sweatpant, elastic and drawcord waist, no visible side stripe. EST.',
                  'Side seam pockets optional (none clearly visible — default is no pocket; supplier may add an in-seam pocket on proto). EST.',
                  'Clean hem, 1 in. Full length over a sneaker. EST.',
              ] + _C_STITCH,
              _pant_poms(waist=28.0, hip=41.0, thigh=25.5, knee=20.0, hem=18.0, inseam=30.5, outseam=40.5, rise_f=11.5, rise_b=15.5),
              'Heather Grey', (0.38, 0.52, 0.62, 0.80),
              bom=[('Fleece / terry', '1', 'Cotton-blend fleece, heather grey', 'Body'),
                   ('Waist elastic', '1', 'Soft elastic, 1–1¼ in, enclosed', 'Waist'),
                   ('Drawcord', '1', 'Self or flat cotton cord, with aglets', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-009', name='Dark Grey Cami & Faded Wide Jean', outfit_id='outfit-8', outfit_label='Outfit 6',
    slug='outfit-6-dark-grey-cami-faded-wide-jean', kind='set',
    tagline='Charcoal lace-trim cami and faded wide jean',
    default_color='Charcoal',
    colors=['Charcoal', 'Faded Blue-Grey Denim'],
    image_extra='Reference frames are from Jordan’s Outfit 6 sheet (asset id outfit-8), registered to her base. Some views are generated edits or mirrors so the bag stays on her left shoulder at every angle — use the photographs as a styling reference only. The bag itself is not a garment in this pack.',
    accessories='The brown leather belt and the brown shoulder bag in the photographs are styling accessories. They are not graded and are not in the apparel BOM. Sneakers are also styling only.',
    fit_notes='The cami is a close crop with a lace neckline and skinny straps. The jean is a mid-rise, faded wide/flare leg, worn with a belt (belt not supplied). First proto in size M.',
    pieces=[
        piece('top', 'Lace-trim cami crop', 'crop-cami-lace',
              _F_STRETCH.format(color='dark charcoal / near-black'),
              [
                  'Fitted cami crop with a lace or picot trim at the neckline, skinny straps, clean hem. EST.',
                  'Lined bust. No hardware on the face. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.5, under=27.5, hem=27.5, cf=11.0, strap=0.4, neck=6.0),
              'Charcoal', (0.40, 0.26, 0.60, 0.40),
              bom=[('Self fabric', '1', 'Stretch knit, charcoal', 'Body, lining'),
                   ('Lace trim', 'as needed', 'Narrow stretch lace, charcoal or black, to match', 'Neckline'),
                   ('Straps', '2', 'Self or elastic, skinny', 'Shoulders')]),
        piece('bottom', 'Faded wide jean', 'jean-wide',
              _F_DENIM.format(color='faded mid blue-grey, with light whiskering as photographed'),
              [
                  'Mid-rise wide/flare jean, zip fly, button, belt loops, back pockets. EST.',
                  'Faded wash with modest whiskering; no heavy rips. Full length over a sneaker. EST.',
              ] + _C_STITCH,
              _pant_poms(waist=28.5, hip=40.0, thigh=23.5, knee=17.0, hem=19.5, inseam=31.0, outseam=41.0, rise_f=10.75, rise_b=15.0),
              'Faded Blue-Grey Denim', (0.38, 0.55, 0.62, 0.82),
              bom=[('Denim', '1', '10–12 oz cotton denim, faded blue-grey', 'Body, pockets'),
                   ('Pocketing', 'as needed', 'Light cotton pocketing', 'Pockets'),
                   ('Zip fly + button', '1 set', 'Antique brass or silver jean trim', 'CF, waist'),
                   ('Belt loops', '5–6', 'Self denim', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-010', name='Black Halter & Ruched Mini Skirt', outfit_id='outfit-9', outfit_label='Outfit 7',
    slug='outfit-7-black-halter-ruched-mini', kind='set',
    tagline='Black draped halter crop and side-ruched mini skirt',
    default_color='Black',
    colors=['Black'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 7. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Black strappy heels are styling only and are not in this BOM.',
    fit_notes='A close, slightly shiny black set. The halter has a draped cowl front and an open, tie back. The mini is very short, with side ruching ties. First proto in size M. Confirm coverage on the fit model before a size set.',
    pieces=[
        piece('top', 'Draped halter crop', 'crop-halter-cowl',
              _F_SATIN.format(color='black') + ' A coated or wet-look stretch knit is also acceptable if the drape matches the photograph. EST.',
              [
                  'Halter with a draped cowl or bias front, skinny ties at the nape and at the back bodice, as photographed. EST.',
                  'Lined bust. Crop length, open back. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.5, under=27.0, hem=27.0, cf=9.75, strap=0.4, neck=5.0),
              'Black', (0.40, 0.26, 0.60, 0.40),
              bom=[('Self fabric', '1', 'Black satin, charmeuse, or wet-look stretch', 'Body, ties, lining'),
                   ('Thread', 'as needed', 'Black', 'Seams')]),
        piece('bottom', 'Side-ruched mini skirt', 'skirt-ruched',
              _F_SATIN.format(color='black, to match the halter') + ' A stretch mesh overlay, if used, should stay close to the photograph. EST.',
              [
                  'Very short mini with side ruching and hanging ties, as photographed. Low-to-mid rise. EST.',
                  'Lined. Side seams hold the ruching channel or rings. Hem coverage must be confirmed on proto. EST.',
              ] + _C_STITCH,
              [
                  pom('H', 'Waist circumference', 'Around the waist, laid flat × 2, relaxed.', 27.0, 'waist'),
                  pom('I', 'Hip circumference', 'Around the seat, laid flat × 2.', 37.5, 'circ'),
                  pom('J', 'Center-front length', 'CF waist to front hem, after ruching is set.', 11.5, 'len'),
                  pom('K', 'Center-back length', 'CB waist to back hem, after ruching is set.', 12.0, 'len'),
                  pom('L', 'Side length, ruched', 'Side waist to hem, with ties at the photographed length.', 11.0, 'len'),
                  pom('M', 'Hem circumference', 'Around the hem, laid flat × 2.', 38.0, 'circ'),
              ],
              'Black', (0.38, 0.44, 0.62, 0.54),
              bom=[('Self fabric', '1', 'Black satin or stretch, to match the halter', 'Body, lining, ties'),
                   ('Waist elastic or zip', '1', 'Invisible side zip or enclosed elastic — confirm on proto (default: enclosed elastic)', 'Waist')]),
    ],
))


_add(dict(
    id='AVA-011', name='Black Sports Bra & Running Short', outfit_id='outfit-10', outfit_label='Outfit 8',
    slug='outfit-8-black-sports-bra-running-short', kind='set',
    tagline='Black sports bra and running short (unbranded equivalent)',
    default_color='Black',
    colors=['Black'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 8. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='White crew socks and sneakers are styling only and are not in this BOM.',
    caveats=[
        'The reference photographs show a third-party swoosh on the bra and on the short. Those marks are not part of this style. This pack specifies an unbranded equivalent. Do not reproduce any third-party trademark, logo or trade dress.',
    ],
    fit_notes='A close sports bra with a racer or standard back, and a short running short with a brief liner and a small side split. First proto in size M. No logos.',
    pieces=[
        piece('top', 'Sports bra (unbranded)', 'sports-bra',
              _F_STRETCH.format(color='black'),
              [
                  'Medium-support sports bra, lined, wide underbust band, racer or close back as photographed. EST.',
                  'No logos, heat transfers or third-party marks. EST.',
                  'Optional removable cups. Clean-finish neck and armhole. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=31.5, under=27.5, hem=27.5, cf=9.25, strap=1.25, neck=6.5),
              'Black', (0.40, 0.24, 0.60, 0.38),
              bom=[('Self fabric', '1', 'Performance stretch knit, black', 'Body, lining, band'),
                   ('Band elastic', '1', 'Soft elastic, enclosed in the underbust band', 'Band')]),
        piece('bottom', 'Running short (unbranded)', 'run-short',
              _F_STRETCH.format(color='black') + ' A lightweight woven running short with a knit brief is also acceptable if the silhouette matches. EST.',
              [
                  'Short running short, elastic waist, inner brief or liner, small side split, as photographed. EST.',
                  'No logos. Drawcord inside the waist optional. EST.',
                  'Clean hem. Inseam about 2½–3 in. EST.',
              ] + _C_STITCH,
              _short_poms(waist=26.5, hip=38.0, thigh=24.0, inseam=2.75, outseam=10.0, rise_f=9.5, rise_b=13.5, hem=24.0),
              'Black', (0.38, 0.44, 0.62, 0.54),
              bom=[('Shell', '1', 'Black stretch knit or light running woven', 'Body'),
                   ('Liner', '1', 'Soft brief knit, black', 'Brief'),
                   ('Waist elastic', '1', 'Soft elastic, enclosed', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-012', name='Leather Moto Suit', outfit_id='outfit-11', outfit_label='Outfit 9',
    slug='outfit-9-leather-moto-suit', kind='suit',
    tagline='Color-blocked leather moto jacket and pant, with knee armor',
    default_color='Black / Racing Red / Off White',
    colors=['Black', 'Racing Red', 'Off White'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 9. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='The moto boots in the photographs are styling only and are not in this apparel BOM. The black crop worn under the jacket may be supplied as a simple unbranded underlayer (see the third piece) or omitted if the jacket is worn closed.',
    fit_notes='A close, two-piece moto set in black leather (or equivalent) with racing-red and off-white panels and knee armor. First proto in size M. This is a fashion moto, not a certified riding suit — do not claim CE or road-safety certification unless the supplier tests and labels it as such.',
    caveats=[
        'Fashion moto styling only. Armor pockets are shown because they appear in the photographs; any protective claim needs a separate, tested specification. EST.',
    ],
    pieces=[
        piece('jacket', 'Color-blocked moto jacket', 'moto-jacket',
              _F_LEATHER.format(color='black, with racing-red and off-white panels'),
              [
                  'Fitted, waist-length moto jacket, CF zip, stand or small collar, long sleeve with a zip cuff. EST.',
                  'Color-blocked red and off-white panels as photographed (shoulder, sleeve, side). Quilted or padded upper sleeve optional, to match the photograph. EST.',
                  'Lined. Two zip hand pockets optional. No third-party marks. EST.',
              ] + _C_STITCH,
              [
                  pom('A', 'Bust circumference', 'Around the bust, jacket closed, laid flat × 2.', 36.5, 'circ'),
                  pom('B', 'Waist circumference', 'Around the waist, closed, laid flat × 2.', 31.0, 'waist'),
                  pom('C', 'Hem circumference', 'Around the hem, laid flat × 2.', 34.0, 'circ'),
                  pom('D', 'Center-back length', 'Nape to CB hem.', 21.0, 'len'),
                  pom('E', 'Shoulder width', 'Across the back, seam to seam.', 15.0, 'small'),
                  pom('F', 'Sleeve length', 'Shoulder point to cuff.', 23.5, 'sleeve'),
                  pom('G', 'Bicep circumference', '1 in below the armhole, laid flat × 2.', 12.5, 'mid'),
              ],
              'Black', (0.36, 0.22, 0.50, 0.42),
              bom=[('Leather or alternative, black', '1', '1.0–1.2 mm garment leather or approved alternative', 'Body, sleeves'),
                   ('Contrast leather, racing red', 'as needed', 'To match the photographed panels', 'Panels'),
                   ('Contrast leather, off-white', 'as needed', 'To match the photographed panels', 'Panels'),
                   ('Lining', '1', 'Satin or mesh lining, black', 'Body, sleeves'),
                   ('CF zipper', '1', 'Separating metal zip, black or antique silver, full CF', 'Center front'),
                   ('Cuff zips', '2', 'Short metal zips', 'Cuffs')]),
        piece('pant', 'Moto pant with knee armor pockets', 'moto-pant',
              _F_LEATHER.format(color='black, with racing-red and off-white side panels'),
              [
                  'Slim moto pant, mid rise, zip fly or a side/CF zip, tapered leg with a zip at the hem if needed to clear a boot. EST.',
                  'Color-blocked side panels as photographed. External knee armor pockets / pads as photographed — fashion pads by default, not a certified protector, unless the supplier submits a tested armor. EST.',
              ] + _C_STITCH,
              _pant_poms(waist=28.5, hip=39.5, thigh=22.5, knee=15.5, hem=13.0, inseam=30.5, outseam=40.5, rise_f=10.5, rise_b=15.0),
              'Black', (0.40, 0.50, 0.60, 0.75),
              bom=[('Leather or alternative, black', '1', 'Same family as the jacket', 'Body'),
                   ('Contrast panels', 'as needed', 'Racing red and off-white, to match the jacket', 'Sides'),
                   ('Lining', '1', 'Slide lining at the knee and seat', 'Knee, seat'),
                   ('Armor pockets / pads', '2', 'Fashion knee pads or tested CE pads if certified', 'Knees'),
                   ('Zips / hardware', 'as needed', 'Black or antique silver', 'Fly, hems')]),
        piece('under', 'Black underlayer crop (optional)', 'crop-tank',
              _F_STRETCH.format(color='black'),
              [
                  'Simple close black crop or bralette, as worn under the open jacket in the photographs. Optional in the bulk order. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.0, under=27.5, hem=27.5, cf=9.5, strap=0.75, neck=6.5),
              'Black', (0.44, 0.30, 0.56, 0.38),
              bom=[('Self fabric', '1', 'Black stretch knit', 'Body')]),
    ],
))

_add(dict(
    id='AVA-013', name='Black Pantsuit & White Shirt', outfit_id='outfit-12', outfit_label='Outfit 10',
    slug='outfit-10-black-pantsuit-white-shirt', kind='suit',
    tagline='Black single-breasted pantsuit with a white shirt',
    default_color='Black',
    colors=['Black', 'White'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 10. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Black pumps and the gold-buckle belt in the photographs are styling only. The belt is not in the apparel BOM.',
    fit_notes='A close, single-breasted black jacket with a white shirt worn open at the throat, and a mid-rise slight-flare trouser. First proto in size M. Tailoring ease is light — this is not an oversized suiting block.',
    pieces=[
        piece('jacket', 'Single-breasted blazer', 'blazer',
              _F_SUITING.format(color='black'),
              [
                  'Single-breasted, two-button jacket, notched lapel, fitted waist, long sleeve with buttons at the cuff, as photographed. EST.',
                  'Front flap or jetted pockets. Back vent (single) unless the supplier prefers none — confirm on proto. Fully lined. EST.',
                  'Light shoulder pad optional. No contrast piping. EST.',
              ] + _C_STITCH,
              [
                  pom('A', 'Bust circumference', 'Around the bust, jacket closed, laid flat × 2.', 37.5, 'circ'),
                  pom('B', 'Waist circumference', 'Around the waist, closed, laid flat × 2.', 32.0, 'waist'),
                  pom('C', 'Hip / hem circumference', 'Around the hem, laid flat × 2.', 40.0, 'circ'),
                  pom('D', 'Center-back length', 'Nape to CB hem.', 24.5, 'len'),
                  pom('E', 'Shoulder width', 'Across the back, seam to seam.', 15.25, 'small'),
                  pom('F', 'Sleeve length', 'Shoulder point to cuff.', 23.5, 'sleeve'),
                  pom('G', 'Bicep circumference', '1 in below the armhole, laid flat × 2.', 13.0, 'mid'),
                  pom('Q', 'Lapel width, at the break', 'Widest point of the lapel.', 3.0, 'hold'),
              ],
              'Black', (0.30, 0.22, 0.48, 0.50),
              bom=[('Suiting, black', '1', 'Wool-blend or viscose suiting, 220–280 g/m²', 'Body, sleeves, undercollar'),
                   ('Lining', '1', 'Bemberg or polyester lining, black', 'Body, sleeves'),
                   ('Canvas / fusible', 'as needed', 'Light fused or half-canvas front', 'Fronts'),
                   ('Buttons', '6–8', 'Black horn-look, 2 CF + cuff', 'CF, cuffs'),
                   ('Shoulder pads', '1 pair', 'Light, optional', 'Shoulders')]),
        piece('shirt', 'White shirt', 'blouse',
              _F_SHIRTING.format(color='white / optic white'),
              [
                  'Classic collar, CF button front, long sleeve with a barrel cuff, slightly fitted through the waist, as worn open at the top in the photographs. EST.',
                  'Yoke at the back. Shirttail or a clean straight hem — default is a slightly curved shirttail. EST.',
              ] + _C_STITCH,
              [
                  pom('A', 'Bust circumference', 'Around the bust, buttoned, laid flat × 2.', 38.0, 'circ'),
                  pom('B', 'Waist circumference', 'Around the waist, buttoned, laid flat × 2.', 34.0, 'waist'),
                  pom('C', 'Hem circumference', 'Around the hem, laid flat × 2.', 39.0, 'circ'),
                  pom('D', 'Center-back length', 'Nape to CB hem.', 26.0, 'len'),
                  pom('E', 'Shoulder width', 'Across the back, seam to seam.', 15.0, 'small'),
                  pom('F', 'Sleeve length', 'Shoulder point to cuff edge.', 23.5, 'sleeve'),
                  pom('G', 'Collar stand height', 'Finished stand, at CB.', 1.25, 'hold'),
                  pom('R', 'Cuff height', 'Finished cuff.', 2.25, 'hold'),
              ],
              'White', (0.44, 0.28, 0.54, 0.40),
              bom=[('Shirting, white', '1', 'Cotton or cotton-blend shirting, 100–120 g/m²', 'Body, sleeves, collar, cuffs'),
                   ('Interlining', 'as needed', 'Collar and cuff fusible', 'Collar, cuffs'),
                   ('Buttons', '10–12', 'White pearl-look, 11–12 ligne', 'CF, cuffs')]),
        piece('pant', 'Mid-rise flare trouser', 'trouser',
              _F_SUITING.format(color='black, to match the jacket'),
              [
                  'Mid-rise trouser, slim through the hip, slight flare from the knee, clean hem over a pump. EST.',
                  'Hook-and-bar plus a zip fly, belt loops (the photographed belt is styling only). Side pockets optional — default is a clean front with a back welt or no back pocket. Lined to the knee if the cloth needs it. EST.',
              ] + _C_STITCH,
              _pant_poms(waist=28.5, hip=39.5, thigh=23.0, knee=16.5, hem=18.5, inseam=31.0, outseam=41.0, rise_f=10.75, rise_b=15.0),
              'Black', (0.38, 0.55, 0.62, 0.85),
              bom=[('Suiting, black', '1', 'Same cloth as the jacket', 'Body'),
                   ('Pocketing / lining', 'as needed', 'To match', 'Pockets, knee lining'),
                   ('Hook, bar, zip', '1 set', 'Black or gunmetal', 'CF fly'),
                   ('Belt loops', '5', 'Self cloth', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-014', name='Black Crop Tank & Pink Satin Short', outfit_id='outfit-15', outfit_label='Outfit 11',
    slug='outfit-11-black-crop-tank-pink-satin-short', kind='set',
    tagline='Black crop tank and dusty-rose satin short',
    default_color='Black',
    colors=['Black', 'Dusty Rose'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 11. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Barefoot in the reference photographs. No additional garments in this pack.',
    fit_notes='A close black crop tank with narrow straps, and a short dusty-rose satin booty short with a drawcord and a small side split. First proto in size M.',
    pieces=[
        piece('top', 'Black crop tank', 'crop-tank',
              _F_STRETCH.format(color='black'),
              [
                  'Fitted crop tank, straight-to-slight-scoop neck, narrow straps, clean hem, as photographed. EST.',
                  'Lined bust optional. No logos. EST.',
              ] + _C_STITCH,
              _knit_crop_poms(bust=32.5, under=28.0, hem=28.0, cf=11.0, strap=0.7, neck=6.5),
              'Black', (0.40, 0.26, 0.60, 0.40),
              bom=[('Self fabric', '1', 'Black stretch knit', 'Body, lining')]),
        piece('bottom', 'Dusty-rose satin short', 'satin-short',
              _F_SATIN.format(color='dusty rose / muted pink'),
              [
                  'Short satin booty short, elastic and drawcord waist, small side split, slightly fluted or clean hem, as photographed. EST.',
                  'Lined in a matching lightweight tricot or self. EST.',
              ] + _C_STITCH,
              _short_poms(waist=26.0, hip=37.5, thigh=23.0, inseam=2.5, outseam=9.0, rise_f=9.0, rise_b=13.0, hem=22.0),
              'Dusty Rose', (0.38, 0.46, 0.62, 0.54),
              bom=[('Satin, dusty rose', '1', 'Acetate or polyester satin, 80–120 g/m²', 'Body'),
                   ('Lining', '1', 'Matching tricot or self', 'Lining'),
                   ('Waist elastic', '1', 'Soft elastic, enclosed', 'Waist'),
                   ('Drawcord', '1', 'Self satin or a matching cord', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-015', name='Grey Tie-Dye Tee & Short', outfit_id='outfit-16', outfit_label='Outfit 12',
    slug='outfit-12-grey-tie-dye-tee-short', kind='set',
    tagline='Oversized grey spiral tie-dye tee and light-grey short',
    default_color='Grey Tie-Dye',
    colors=['Grey Tie-Dye', 'Light Grey'],
    image_extra='All eight frames are Jordan’s exact reference turnaround for Outfit 12. Angles 225° and 315° are horizontal mirrors of 135° and 45°.',
    accessories='Barefoot in the reference photographs. No additional garments in this pack.',
    fit_notes='The tee is oversized, drop-shoulder, and mid-hip, in a grey/cream spiral tie-dye. The short is a light-grey casual booty/french-terry short. First proto in size M (the tee is already a relaxed fit on this body).',
    caveats=[
        'The tie-dye is a photographic reference only. A lab dip and a strike-off of the spiral must be approved before a bulk dye lot. Placement of the spiral will vary; do not expect a garment-for-garment match to the photograph.',
    ],
    pieces=[
        piece('top', 'Oversized spiral tie-dye tee', 'tee-oversized',
              'Cotton or cotton-blend jersey, ~160–180 g/m², garment-dyed in a grey/cream spiral as photographed. EST.',
              [
                  'Oversized, dropped shoulder, short sleeve, mid-hip length, as photographed. EST.',
                  'Rib or self neckband, ~⅝ in. Clean hem and sleeve hem, ¾–1 in. EST.',
                  'Tie-dye after construction or a printed equivalent — confirm on proto. EST.',
              ] + _C_STITCH,
              [
                  pom('A', 'Chest circumference', 'Around the chest, laid flat × 2.', 42.0, 'circ'),
                  pom('B', 'Hem circumference', 'Around the hem, laid flat × 2.', 42.0, 'circ'),
                  pom('C', 'Center-back length', 'Nape to CB hem.', 25.0, 'len'),
                  pom('D', 'Shoulder / drop-shoulder width', 'Across the back, seam to seam.', 19.5, 'small'),
                  pom('E', 'Sleeve length, from dropped seam', 'Dropped shoulder seam to sleeve hem.', 8.0, 'sleeve'),
                  pom('F', 'Armhole (straight)', 'Straight armhole, laid flat.', 9.5, 'small'),
                  pom('G', 'Neck opening, laid flat', 'Half the neck, laid flat.', 7.0, 'small'),
              ],
              'Grey Tie-Dye', (0.36, 0.28, 0.50, 0.42),
              bom=[('Jersey, to be dyed', '1', 'Cotton/cotton-blend jersey, 160–180 g/m²', 'Body, sleeves'),
                   ('Neck rib', 'as needed', 'Matching or self', 'Neckband')]),
        piece('bottom', 'Light-grey casual short', 'terry-short',
              _F_SWEAT.format(color='light grey / oatmeal-grey') + ' A light jersey short is also acceptable. EST.',
              [
                  'Short casual short, elastic or drawcord waist, close through the seat, as photographed. EST.',
                  'Clean or slightly raw hem. No logos. EST.',
              ] + _C_STITCH,
              _short_poms(waist=26.5, hip=37.5, thigh=23.0, inseam=2.5, outseam=9.0, rise_f=9.25, rise_b=13.25, hem=21.0),
              'Light Grey', (0.40, 0.52, 0.60, 0.58),
              bom=[('Fleece or jersey, light grey', '1', 'To match the paler grey of the photograph', 'Body'),
                   ('Waist elastic', '1', 'Soft elastic, enclosed', 'Waist')]),
    ],
))

_add(dict(
    id='AVA-016', name='USA Home Kit', outfit_id='usa-jersey', outfit_label='USA jersey',
    slug='usa-jersey-home-kit', kind='jersey',
    tagline='White soccer jersey and short, navy and red trim',
    default_color='White',
    colors=['White', 'Navy', 'Red'],
    image_extra='These frames come from an AI-generated 6-view sheet (not a photographed physical sample), dressed onto Model 1 from her own base turnaround. Angles 225° and/or 315° include a mirror or a mirrored edit. Treat every construction, fabric and color call as an estimate from the image only.',
    accessories='Barefoot in the reference images. No additional garments in this pack.',
    caveats=[
        'The crest, stripes and any “USA” lettering in the images resemble a national-team home kit. This pack is a visual reference for a white / navy / red soccer kit silhouette only. Official federation, national-team, or third-party marks must not be used without a license. Supplier to set a blank chest or an Atelier 360 crest pending licensed artwork.',
        'The images are generated, not a physical sample. Confirm color, stripe placement and fit on a first proto.',
    ],
    fit_notes='A close women’s soccer jersey with a navy/red rib collar and cuffs, a navy side panel, and a matching white short with a navy side stripe. First proto in size M. No licensed marks.',
    pieces=[
        piece('top', 'White soccer jersey', 'jersey',
              _F_JERSEY_KIT.format(color='white, with navy and red trim'),
              [
                  'Short-sleeve women’s soccer jersey, close fit, crew rib collar in navy/red, rib cuffs, navy side panel as photographed. EST.',
                  'Chest crest area is a placeholder only — no official mark. A small woven or printed label may sit at the lower left hem. EST.',
                  'Clean hem. Heat-seal or overlocked seams typical of a kit garment. EST.',
              ] + _C_STITCH,
              [
                  pom('A', 'Chest circumference', 'Around the chest, laid flat × 2.', 35.0, 'circ'),
                  pom('B', 'Waist circumference', 'Around the waist, laid flat × 2.', 32.0, 'waist'),
                  pom('C', 'Hem circumference', 'Around the hem, laid flat × 2.', 35.0, 'circ'),
                  pom('D', 'Center-back length', 'Nape to CB hem.', 24.0, 'len'),
                  pom('E', 'Shoulder width', 'Across the back, seam to seam.', 15.0, 'small'),
                  pom('F', 'Sleeve length', 'Shoulder point to cuff edge.', 7.25, 'sleeve'),
                  pom('G', 'Collar height', 'Finished rib collar, at CB.', 1.0, 'hold'),
              ],
              'White', (0.40, 0.26, 0.58, 0.40),
              bom=[('Jersey knit, white', '1', 'Performance polyester interlock, 140–160 g/m²', 'Body, sleeves'),
                   ('Navy panel', 'as needed', 'Same cloth, navy', 'Side panels'),
                   ('Collar / cuff rib', 'as needed', 'Navy/red striped rib', 'Collar, cuffs'),
                   ('Crest', '1', 'Blank or Atelier 360 mark only, pending licensed art', 'Left chest')]),
        piece('bottom', 'White kit short', 'jersey-short',
              _F_JERSEY_KIT.format(color='white, with a navy side stripe'),
              [
                  'Short kit short, elastic waist, inner brief, navy side stripe, as photographed. EST.',
                  'A placeholder mark may sit on the left leg — no official crest. EST.',
              ] + _C_STITCH,
              _short_poms(waist=26.5, hip=38.0, thigh=24.0, inseam=3.0, outseam=10.5, rise_f=9.75, rise_b=13.75, hem=23.5),
              'White', (0.38, 0.46, 0.62, 0.56),
              bom=[('Jersey knit, white', '1', 'Same family as the jersey', 'Body'),
                   ('Navy stripe', 'as needed', 'Navy self or tape', 'Side'),
                   ('Brief liner', '1', 'Soft brief knit, white', 'Liner'),
                   ('Waist elastic', '1', 'Soft elastic, enclosed, drawcord optional', 'Waist')]),
    ],
))


def style_by_id(sid):
    return next((s for s in CATALOG if s['id'] == sid), None)


def style_by_outfit(oid):
    return next((s for s in CATALOG if s['outfit_id'] == oid), None)


def order_style_records():
    """Entries for data/styles.json (order builder)."""
    out = []
    for s in CATALOG:
        out.append({
            'id': s['id'],
            'name': s['name'],
            'kind': s['kind'],
            'techpack': f"{s['id']} {s['name']} technical package",
            'season': s.get('season') or SEASON,
            'sizes': list(s['sizes']),
            'sizePrefix': s.get('size_prefix') or '',
            'sizeLabel': s.get('size_label') or 'US size',
            'baseSize': s.get('base_size') or 'M',
            'colors': list(s.get('colors') or [s.get('default_color')]),
            'defaultColor': s.get('default_color') or (s.get('colors') or [''])[0],
            'fitModel': 'Model 1 (exact-26), 5 ft 6 in / 130 lb curvy female, all measures EST. First proto in size M.',
            'units': 'in',
            'outfitId': s['outfit_id'],
            'outfitLabel': s['outfit_label'],
            'collection': 'Model 1',
        })
    return out


# ---------------------------------------------------------------------------
# Color sampling (general — not limited to greys)
# ---------------------------------------------------------------------------
def _is_bg(p):
    r, g, b = p
    return r > 242 and g > 242 and b > 242


def _is_skin(p):
    r, g, b = p
    if r < 80:
        return False
    return (r > g) and (g >= b - 15) and (r - b) > 20 and (r - g) < 90 and r < 235 and g > 55


def sample_box(im, box):
    w, h = im.size
    x0, y0, x1, y1 = [int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)]
    px = im.convert('RGB').load()
    cols = []
    for y in range(max(0, y0), min(h, y1), 2):
        for x in range(max(0, x0), min(w, x1), 2):
            p = px[x, y]
            if _is_bg(p) or _is_skin(p):
                continue
            cols.append(p)
    if not cols:
        return (180, 180, 180)
    cols.sort()
    return cols[len(cols) // 2]


def rgb_hex(rgb):
    return '#{:02X}{:02X}{:02X}'.format(*rgb)


# ---------------------------------------------------------------------------
# Flats (original line drawings — not patterns, not to scale)
# ---------------------------------------------------------------------------
def _svg_open(w=560, h=250, x=0, y=0):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}" width="100%" '
        f'class="flat" fill="none" stroke="#222" stroke-width="1.35" stroke-linecap="round" '
        f'stroke-linejoin="round">'
    )


def _co(x, y, letter, lx, ly):
    return (
        f'<line x1="{x}" y1="{y}" x2="{lx}" y2="{ly}" stroke="#b08d57" stroke-width="1"/>'
        f'<circle cx="{lx}" cy="{ly}" r="8" fill="#fff" stroke="#b08d57" stroke-width="1.1"/>'
        f'<text x="{lx}" y="{ly + 3.2}" text-anchor="middle" stroke="none" fill="#7a3f0c" '
        f'font-size="9" font-family="Liberation Sans, Helvetica, Arial, sans-serif" font-weight="700">{letter}</text>'
    )


def _label(x, y, t):
    return (
        f'<text x="{x}" y="{y}" stroke="none" fill="#5c5c57" font-size="9" letter-spacing="0.12em" '
        f'font-family="Liberation Sans, Helvetica, Arial, sans-serif" text-anchor="middle">{t}</text>'
    )


def flats_for(piece, accent='#666'):
    """Return an SVG string for a piece kind. Front left, back right."""
    kind = piece.get('kind') or ''
    codes = [p['code'] for p in (piece.get('poms') or [])]
    def C(code, x, y, lx, ly):
        return _co(x, y, code, lx, ly) if (not codes or code in codes) else ''

    body = ''
    vb = (40, 30, 540, 200)
    if kind in ('flare-pant', 'cargo-jean', 'sweat-wide', 'jean-wide', 'trouser', 'moto-pant'):
        vb = (40, 20, 540, 330)
    elif kind in ('blazer', 'blouse', 'tee-oversized', 'jersey', 'moto-jacket'):
        vb = (40, 30, 580, 250)
    elif kind in ('booty-short', 'short-piped', 'run-short', 'satin-short', 'terry-short', 'jersey-short', 'cargo-jort', 'skirt-ruched'):
        vb = (40, 30, 540, 200)
    # Generic two-view canvas: front origin (40,40), back origin (400,40)
    if kind in ('crop-racer', 'sports-bra', 'crop-tank'):
        # front crop
        body += '''
        <path d="M110 70 C120 62 150 62 160 70 L168 90 L175 150 Q135 165 95 150 L102 90 Z"/>
        <path d="M110 70 C100 95 95 115 112 140"/>
        <path d="M160 70 C170 95 175 115 158 140"/>
        <path d="M95 150 L95 168 Q135 180 175 168 L175 150"/>
        '''
        if kind == 'crop-racer':
            body += '<path d="M430 70 C470 70 490 110 490 150 L490 168 Q450 180 410 168 L410 150 C410 110 430 70 470 70" />'
            body += '<path d="M450 70 C445 100 445 120 450 150"/>'
        else:
            body += '''
            <path d="M410 90 L410 168 Q450 180 490 168 L490 90"/>
            <path d="M410 90 C420 70 450 62 470 70 C485 78 494 90 490 90"/>
            <path d="M430 70 L410 90 M470 70 L490 90"/>
            '''
        body += C('A', 135, 120, 210, 110) + C('B', 135, 160, 210, 165)
        body += C('D', 135, 70, 60, 50) + C('F', 108, 78, 60, 90)
        body += _label(135, 205, 'FRONT') + _label(450, 205, 'BACK')
    elif kind in ('crop-zip-hoodie',):
        body += '''
        <path d="M95 80 L105 70 L125 78 L145 70 L155 80 L175 95 L175 175 L95 175 L95 95 Z"/>
        <path d="M125 78 L125 175"/><!-- zip -->
        <path d="M105 70 Q125 48 145 70"/><!-- hood -->
        <path d="M95 95 L60 150 L75 158 L100 120"/>
        <path d="M175 95 L210 150 L195 158 L170 120"/>
        <path d="M110 100 L110 160 M140 100 L140 160"/>
        <path d="M430 80 L440 70 L460 78 L480 70 L490 80 L510 95 L510 175 L430 175 L430 95 Z"/>
        <path d="M440 70 Q460 48 480 70"/>
        <path d="M430 95 L395 150 L410 158 L435 120"/>
        <path d="M510 95 L545 150 L530 158 L505 120"/>
        '''
        body += C('A', 135, 120, 220, 110) + C('D', 135, 80, 60, 50) + C('S', 200, 140, 230, 170)
        body += _label(135, 200, 'FRONT') + _label(470, 200, 'BACK')
    elif kind in ('crop-halter-zip', 'crop-halter-tie', 'crop-halter-cowl', 'crop-cami', 'crop-cami-lace', 'crop-ls-square'):
        if kind == 'crop-ls-square':
            body += '''
            <path d="M100 85 L115 70 L155 70 L170 85 L185 100 L185 170 L85 170 L85 100 Z"/>
            <path d="M115 70 L125 95 L145 95 L155 70"/><!-- square neck -->
            <path d="M135 95 L135 108"/><!-- tie -->
            <path d="M85 100 L50 155 L65 162 L95 120"/>
            <path d="M185 100 L220 155 L205 162 L175 120"/>
            <path d="M430 85 L445 70 L485 70 L500 85 L500 170 L400 170 L400 85 Z"/>
            <path d="M445 70 L445 95 L485 95 L485 70"/>
            <path d="M400 100 L365 155 L380 162 L410 120"/>
            <path d="M500 100 L535 155 L520 162 L490 120"/>
            '''
        elif kind == 'crop-halter-cowl':
            body += '''
            <path d="M115 60 Q135 90 155 60"/>
            <path d="M115 60 L100 100 L95 165 Q135 178 175 165 L175 100 L155 60"/>
            <path d="M135 60 L135 48"/>
            <path d="M430 80 L450 58 L470 80 L490 100 L490 165 Q450 178 410 165 L410 100 Z"/>
            <path d="M450 58 L450 48 M430 80 L470 80"/>
            '''
        elif kind in ('crop-cami', 'crop-cami-lace'):
            body += '''
            <path d="M110 80 L120 68 L150 68 L160 80 L175 155 Q135 168 95 155 Z"/>
            <path d="M120 68 L110 48 M150 68 L160 48"/>
            '''
            if kind == 'crop-cami-lace':
                body += '<path d="M120 68 Q135 78 150 68"/>'
            body += '''
            <path d="M125 80 L125 150"/><!-- optional zip suggestion omitted if lace -->
            <path d="M410 90 L420 70 L460 70 L470 90 L485 155 Q445 168 405 155 Z"/>
            <path d="M420 70 L412 50 M460 70 L468 50"/>
            '''
        else:  # halter zip / tie
            body += '''
            <path d="M115 60 L125 80 L155 80 L165 60"/>
            <path d="M125 80 L95 160 Q135 172 175 160 L155 80"/>
            <path d="M140 80 L140 160"/>
            <path d="M430 85 L450 58 L470 85 L490 160 Q450 172 410 160 Z"/>
            <path d="M450 58 L450 48"/>
            '''
        body += C('A', 135, 120, 210, 110) + C('D', 135, 70, 55, 50) + C('S', 210, 140, 230, 175)
        body += _label(135, 200, 'FRONT') + _label(450, 200, 'BACK')
    elif kind in ('booty-short', 'short-piped', 'run-short', 'satin-short', 'terry-short', 'jersey-short', 'cargo-jort'):
        rise = 70
        body += f'''
        <path d="M100 {rise} L110 {rise-8} L160 {rise-8} L170 {rise} L180 {rise+40} L175 {rise+90} L160 {rise+100} L135 {rise+55} L110 {rise+100} L95 {rise+90} L90 {rise+40} Z"/>
        <path d="M135 {rise+55} L135 {rise-8}"/>
        <path d="M430 {rise} L440 {rise-8} L490 {rise-8} L500 {rise} L510 {rise+40} L505 {rise+90} L490 {rise+100} L465 {rise+55} L440 {rise+100} L425 {rise+90} L420 {rise+40} Z"/>
        <path d="M465 {rise+55} L465 {rise-8}"/>
        '''
        if kind == 'short-piped':
            body += f'<path d="M100 {rise+20} L95 {rise+90} M170 {rise+20} L175 {rise+90}" stroke="#b08d57"/>'
            body += f'<path d="M490 {rise+100} Q465 {rise+70} 440 {rise+100}"/>'
        if kind == 'cargo-jort':
            body += f'<rect x="92" y="{rise+30}" width="28" height="32" rx="2"/><rect x="150" y="{rise+30}" width="28" height="32" rx="2"/>'
            body += f'<rect x="478" y="{rise+30}" width="28" height="32" rx="2"/><rect x="424" y="{rise+36}" width="26" height="28" rx="2"/>'
        if kind == 'run-short':
            body += f'<path d="M95 {rise+90} L90 {rise+70} M175 {rise+90} L180 {rise+70}"/>'
        body += C('H', 135, rise, 60, rise-20) + C('I', 170, rise+40, 220, rise+30) + C('M', 145, rise+80, 220, rise+90)
        body += _label(135, rise+125, 'FRONT') + _label(465, rise+125, 'BACK')
    elif kind in ('flare-pant', 'cargo-jean', 'sweat-wide', 'jean-wide', 'trouser', 'moto-pant'):
        body += '''
        <path d="M115 40 L125 32 L165 32 L175 40 L185 90 L195 200 L190 300 L170 310 L135 200 L100 310 L80 300 L75 200 L85 90 Z"/>
        <path d="M135 200 L135 32"/>
        <path d="M445 40 L455 32 L495 32 L505 40 L515 90 L525 200 L520 300 L500 310 L465 200 L430 310 L410 300 L405 200 L415 90 Z"/>
        <path d="M465 200 L465 32"/>
        '''
        if kind == 'cargo-jean':
            body += '<rect x="80" y="140" width="32" height="40" rx="2"/><rect x="158" y="140" width="32" height="40" rx="2"/>'
            body += '<rect x="488" y="150" width="28" height="32" rx="2"/><rect x="430" y="150" width="28" height="32" rx="2"/>'
        if kind == 'moto-pant':
            body += '<path d="M95 200 L125 210 L125 245 L95 250 Z"/><path d="M175 200 L145 210 L145 245 L175 250 Z"/>'
        if kind == 'sweat-wide':
            body += '<path d="M125 32 Q145 42 165 32"/><!-- drawcord -->'
        body += C('H', 145, 36, 60, 24) + C('I', 180, 90, 230, 80) + C('O', 185, 305, 230, 310) + C('P', 175, 40, 230, 40)
        body += _label(135, 335, 'FRONT') + _label(465, 335, 'BACK')
    elif kind == 'skirt-ruched':
        body += '''
        <path d="M110 50 L120 42 L170 42 L180 50 L200 140 Q145 160 90 140 Z"/>
        <path d="M180 70 L210 70 M180 100 L215 110"/>
        <path d="M430 50 L440 42 L490 42 L500 50 L520 140 Q465 160 410 140 Z"/>
        <path d="M500 70 L530 70"/>
        '''
        body += C('H', 145, 46, 60, 30) + C('J', 145, 50, 60, 150) + C('I', 185, 90, 230, 90)
        body += _label(145, 185, 'FRONT') + _label(465, 185, 'BACK')
    elif kind == 'moto-jacket':
        body += '''
        <path d="M100 70 L115 55 L135 68 L155 55 L170 70 L200 95 L195 190 L100 190 L95 95 Z"/>
        <path d="M135 68 L140 190"/><!-- zip -->
        <path d="M100 95 L60 155 L75 162 L110 115"/>
        <path d="M170 95 L210 155 L195 162 L160 115"/>
        <path d="M115 55 L100 70 M155 55 L170 70"/>
        <path d="M430 70 L445 55 L465 68 L485 55 L500 70 L530 95 L525 190 L430 190 L425 95 Z"/>
        <path d="M430 95 L390 155 L405 162 L440 115"/>
        <path d="M500 95 L540 155 L525 162 L490 115"/>
        <path d="M140 90 L120 80 L120 140 L140 130 Z" /><!-- red panel hint -->
        '''
        body += C('A', 135, 120, 230, 110) + C('D', 135, 55, 60, 40) + C('F', 205, 140, 240, 175)
        body += _label(135, 215, 'FRONT') + _label(465, 215, 'BACK')
    elif kind == 'blazer':
        body += '''
        <path d="M95 75 L115 55 L135 70 L155 55 L175 75 L200 100 L200 210 L155 205 L135 150 L115 205 L70 210 L70 100 Z"/>
        <path d="M135 70 L125 130 L145 130 L135 70"/><!-- lapels -->
        <path d="M120 150 L120 155 M150 150 L150 155"/><!-- buttons -->
        <path d="M95 100 L55 160 L70 168 L110 120"/>
        <path d="M175 100 L215 160 L200 168 L160 120"/>
        <path d="M430 75 L450 55 L470 70 L490 55 L510 75 L535 100 L535 210 L430 210 L430 100 Z"/>
        <path d="M470 210 L470 150"/><!-- vent -->
        <path d="M430 100 L390 160 L405 168 L445 120"/>
        <path d="M510 100 L550 160 L535 168 L495 120"/>
        '''
        body += C('A', 135, 120, 230, 110) + C('D', 135, 55, 50, 40) + C('F', 210, 145, 240, 180) + C('Q', 130, 100, 50, 110)
        body += _label(135, 235, 'FRONT') + _label(470, 235, 'BACK')
    elif kind == 'blouse':
        body += '''
        <path d="M100 80 L120 60 L135 78 L155 78 L170 60 L190 80 L205 100 L200 220 L90 220 L85 100 Z"/>
        <path d="M135 78 L145 78 L145 70 Q140 58 155 58 Q165 58 160 70 L155 78"/>
        <path d="M145 90 L145 200"/><!-- placket -->
        <path d="M100 100 L60 160 L75 168 L115 120"/>
        <path d="M190 100 L230 160 L215 168 L175 120"/>
        <path d="M430 80 L450 60 L490 60 L510 80 L515 100 L520 220 L410 220 L405 100 Z"/>
        <path d="M450 60 L450 80 L490 80 L490 60"/>
        <path d="M430 100 L390 160 L405 168 L445 120"/>
        <path d="M510 100 L550 160 L535 168 L495 120"/>
        '''
        body += C('A', 145, 130, 230, 120) + C('D', 145, 60, 50, 40) + C('F', 220, 145, 250, 180)
        body += _label(145, 245, 'FRONT') + _label(470, 245, 'BACK')
    elif kind in ('tee-oversized', 'jersey'):
        body += '''
        <path d="M80 90 L130 70 L140 85 L170 85 L180 70 L230 90 L250 120 L240 230 L70 230 L60 120 Z"/>
        <path d="M140 85 Q155 95 170 85"/>
        <path d="M80 90 L50 140 L70 150 L100 110"/>
        <path d="M230 90 L260 140 L240 150 L210 110"/>
        <path d="M430 90 L480 70 L490 85 L520 85 L530 70 L580 90 L600 120 L590 230 L420 230 L410 120 Z"/>
        <path d="M490 85 Q505 95 520 85"/>
        <path d="M430 90 L400 140 L420 150 L450 110"/>
        <path d="M580 90 L610 140 L590 150 L560 110"/>
        '''
        if kind == 'jersey':
            body += '<path d="M140 85 Q155 72 170 85"/><rect x="148" y="115" width="16" height="16" rx="2"/>'
        body += C('A', 155, 140, 40, 130) + C('C', 155, 230, 40, 230) + C('D', 155, 70, 40, 50) + C('E', 80, 90, 40, 80)
        body += _label(155, 255, 'FRONT') + _label(505, 255, 'BACK')
    else:
        body += f'<text x="360" y="200" text-anchor="middle" stroke="none" fill="#5c5c57" font-size="11">Flat for {esc(kind)}</text>'
    return _svg_open(w=vb[2], h=vb[3], x=vb[0], y=vb[1]) + body + '</svg>'


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def hdr(st, title):
    return mt.hdr(st['id'], title, st.get('season') or SEASON)


def ftr(st, page, total):
    return mt.ftr(st['id'], page, total)


def pom_table(piece, sizes, base_size):
    head = ''.join(f'<th class="{"base" if sz==base_size else ""}">{esc(sz)}</th>' for sz in sizes)
    rows = []
    for pm in piece['poms']:
        cells = []
        for sz in sizes:
            val = grade(pm['base'], pm['grade'], sz)
            cls = ' class="base"' if sz == base_size else ''
            cells.append(f'<td{cls}>{inch(val)}</td>')
        rows.append(
            f'<tr><td class="code">{esc(pm["code"])}</td><td>{esc(pm["name"])} '
            f'<span class="badge">EST.</span><div class="muted">{esc(pm["how"])}</div></td>'
            + ''.join(cells) + '</tr>'
        )
    return (
        f'<h3>{esc(piece["name"]).upper()}</h3>'
        f'<table class="pom"><thead><tr><th>POM</th><th>Description</th>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def views_grid(angles, captions):
    cells = []
    for a in angles:
        cap = captions.get(a, f'{a:03d}°')
        cells.append(
            f'<figure><img src="img/{a:03d}.jpg" alt="{esc(cap)}"/><figcaption>{esc(cap)}</figcaption></figure>'
        )
    return '<div class="views">' + ''.join(cells) + '</div>'


def build_html(ctx):
    st, prof, pages_meta = ctx['style'], ctx['profile'], ctx
    v = prof.get('values') or {}
    name = prof.get('name') or 'Fit model'
    ht, wt = v.get('height'), v.get('weight')
    ht_s = f"{int(ht)//12} ft {int(ht)%12} in" if ht else '—'
    pieces = st['pieces']
    colors = pages_meta['colors']  # {piece_id: (rgb, pantone, hex)}
    n_pages = pages_meta['n_pages']
    caveats = st.get('caveats') or []
    caveat_html = ''.join(f'<p class="note">{esc(c)}</p>' for c in caveats)
    piece_list = ', '.join(p['name'] for p in pieces)
    outfit_line = f"{st['outfit_label']}" + (f"  ·  gallery id {st['outfit_id']}" if st['outfit_id'] else '')

    def src(key):
        return pages_meta['imgs'].get(key, '')

    # cover colors
    swatches = []
    for p in pieces:
        rgb, pant, hx = colors[p['id']]
        swatches.append(
            f'<div class="sw"><img src="img/swatch-{p["id"]}.png" alt=""/><div>'
            f'<b>{esc(p["color_name"])}</b><div class="muted">{esc(hx)}  ·  approx. {esc(pant)}</div>'
            f'<div class="muted">{esc(p["name"])}</div></div></div>'
        )

    page = 0
    extra_css = (
        '.views{display:grid;grid-template-columns:repeat(4,1fr);gap:6pt;}'
        '.views figure{margin:0;background:var(--wash);border:0.4pt solid var(--rule);padding:4pt;}'
        '.views img{width:100%;height:auto;display:block;}'
        '.views figcaption{font-size:6.5pt;color:var(--muted);text-align:center;margin-top:3pt;letter-spacing:.06em;}'
        '.details{display:grid;grid-template-columns:repeat(3,1fr);gap:6pt;}'
        '.details figure{margin:0;background:var(--wash);border:0.4pt solid var(--rule);padding:4pt;}'
        '.details img{width:100%;height:1.9in;object-fit:cover;display:block;}'
        '.flats{display:grid;grid-template-columns:1fr;gap:8pt;}'
        '.flats .card{border:0.4pt solid var(--rule);padding:6pt 8pt;}'
        '.flat{max-height:2.7in;width:100%;}.flats.tight .flat{max-height:1.62in;}.flats.tight .card{padding:4pt 6pt;}'
        '.sw{display:flex;gap:8pt;align-items:center;margin:4pt 0;}'
        '.sw img{width:36pt;height:36pt;border:0.4pt solid var(--rule);}'
        'table.pom td,table.pom th{text-align:center;padding:2pt 3pt;} table.pom h3,h3{margin-top:6pt;}'
        'table.pom td.code,table.pom th:first-child,table.pom td:nth-child(2),table.pom th:nth-child(2){text-align:left;}'
        'table.pom th.base,table.pom td.base{background:#ebeae5;font-weight:700;}'
        'table.pom .muted{font-size:6.2pt;}'
        '.note{border-left:2pt solid var(--est);padding:3pt 8pt;color:var(--est);font-size:7.5pt;margin:4pt 0 8pt;}'
        'table.meta th{width:1.55in;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-size:6.6pt;font-weight:700;border:none;border-bottom:0.4pt solid var(--rule);background:none;padding:3pt 8pt 3pt 0;}'
        'table.meta td{border:none;border-bottom:0.4pt solid var(--rule);background:none;}'
        'ol.con li, ul.con li{margin:0 0 3pt 14pt;}'
    )
    parts = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>'
             f'<title>{esc(st["id"])} {esc(st["name"])} — Technical package</title>'
             '<style>' + mt.CSS + extra_css + '</style></head><body>']

    # 1 cover
    page += 1
    parts.append(f'<section class="page">{hdr(st, "01  ·  Cover")}<h1>{esc(st["name"])}</h1>'
                 f'<p class="muted">{esc(st["id"])}  ·  {esc(outfit_line)}  ·  {esc(st["tagline"])}</p>'
                 f'<div style="display:grid;grid-template-columns:1.7in 1fr;gap:12pt;margin:8pt 0 8pt;">'
                 f'<img src="img/000.jpg" alt="Front reference" style="width:100%;border:0.4pt solid var(--rule);"/>'
                 f'<div><table class="meta">'
                 f'<tr><th>Designer</th><td>{esc(DESIGNER)}</td></tr>'
                 f'<tr><th>Season</th><td>{esc(st.get("season") or SEASON)}</td></tr>'
                 f'<tr><th>Date</th><td>{TODAY}</td></tr>'
                 f'<tr><th>Fit model</th><td>Model 1 (exact-26). {esc(ht_s)}, {inch(wt)} lb. Every measure EST. First proto in size {esc(st["base_size"])}.</td></tr>'
                 f'<tr><th>Pieces</th><td>{esc(piece_list)}</td></tr>'
                 f'<tr><th>Sizes</th><td>{esc(st["size_label"])} {", ".join(st["sizes"])}. First proto in {esc(st["base_size"])}.</td></tr>'
                 f'<tr><th>Units</th><td>Inches and US sizes. Laid-flat widths are doubled for circumferences.</td></tr>'
                 f'</table>{caveat_html}'
                 f'<p class="note">Every POM, fabric, construction call and color reference in this pack is an <b>estimate</b> inferred from the photographs and from standard female proportions at 5 ft 6 in / 130 lb. Nothing here is a tape-measured sample or a lab dip. Supplier to confirm on a first proto before a bulk cut.</p>'
                 f'</div></div>'
                 f'<div>{"".join(swatches)}</div>'
                 f'{ftr(st, page, n_pages)}</section>')

    # 2 turnaround
    page += 1
    caps = pages_meta['captions']
    parts.append(f'<section class="page">{hdr(st, "02  ·  Reference views")}'
                 f'<h2>360 REFERENCE  ·  MODEL 1</h2>'
                 f'<p class="note">{esc(st.get("image_extra") or "Reference views from the live gallery.")} Image crops are photographic references, not a graded sample.</p>'
                 f'{views_grid((0,45,90,135,180,225,270,315), caps)}'
                 f'{ftr(st, page, n_pages)}</section>')

    # 3 details
    page += 1
    dets = pages_meta.get('details') or []
    dhtml = ''.join(
        f'<figure><img src="{esc(fn)}" alt="{esc(cap)}"/><figcaption>{esc(cap)}</figcaption></figure>'
        for fn, cap in dets
    )
    parts.append(f'<section class="page">{hdr(st, "03  ·  Detail references")}'
                 f'<h2>DETAIL CROPS</h2>'
                 f'<p class="muted">Crops from the same reference frames. Use them for seam, pocket, trim and color placement only — they are not a construction sample.</p>'
                 f'<div class="details">{dhtml}</div>'
                 f'<p class="note" style="margin-top:10pt">{esc(st.get("accessories") or "")}</p>'
                 f'{ftr(st, page, n_pages)}</section>')

    # 4 flats
    page += 1
    flats = ''.join(
        f'<div class="card"><h3>{esc(p["name"]).upper()}</h3>{flats_for(p)}</div>'
        for p in pieces
    )
    parts.append(f'<section class="page">{hdr(st, "04  ·  Flats")}'
                 f'<h2>FLAT SKETCHES  ·  NOT A PATTERN, NOT TO SCALE</h2>'
                 f'<p class="note">Original line drawings made for this pack. They describe construction intent only. Callout letters match the POM chart.</p>'
                 f'<div class="flats{" tight" if len(pieces)>=3 else ""}">{flats}</div>'
                 f'{ftr(st, page, n_pages)}</section>')

    # 5 BOM
    page += 1
    bom_rows = []
    for p in pieces:
        for item, qty, desc, use in (p.get('bom') or []):
            bom_rows.append(
                f'<tr><td>{esc(p["name"])}</td><td>{esc(item)}</td><td>{esc(qty)}</td>'
                f'<td>{esc(desc)} <span class="badge">EST.</span></td><td>{esc(use)}</td></tr>'
            )
    parts.append(f'<section class="page">{hdr(st, "05  ·  Bill of materials")}'
                 f'<h2>BILL OF MATERIALS</h2>'
                 f'<p class="note">All materials are proposed from the photographs. Supplier to submit a swatch, a lab dip and a trim card before proto cutting.</p>'
                 f'<table><thead><tr><th>Piece</th><th>Item</th><th>Qty</th><th>Description</th><th>Use</th></tr></thead>'
                 f'<tbody>{"".join(bom_rows)}</tbody></table>'
                 f'<h2 style="margin-top:12pt">FABRIC INTENT</h2>'
                 + ''.join(f'<p><b>{esc(p["name"])}.</b> {esc(p["fabric"])}</p>' for p in pieces)
                 + f'{ftr(st, page, n_pages)}</section>')

    # 6 construction
    page += 1
    cons = []
    for p in pieces:
        cons.append(f'<h3>{esc(p["name"]).upper()}</h3><ul class="con">'
                    + ''.join(f'<li>{esc(c)}</li>' for c in p['construction']) + '</ul>')
    parts.append(f'<section class="page">{hdr(st, "06  ·  Construction")}'
                 f'<h2>CONSTRUCTION  ·  ALL EST.</h2>'
                 f'<p class="note">Methods are proposed so a first proto can be cut. The supplier may recommend an equivalent method; confirm in writing on the proto.</p>'
                 + ''.join(cons)
                 + f'{ftr(st, page, n_pages)}</section>')

    # 7 (and 8, if needed) POM
    pom_intro = (
        f'<h2>POINTS OF MEASURE  ·  {esc(st["size_label"]).upper()}  ·  INCHES</h2>'
        f'<p class="note">Base column ({esc(st["base_size"])}) is shaded. Every POM is <span class="badge">EST.</span> '
        f'Graded from the Model 1 5 ft 6 in / 130 lb female fit profile (bust 36, waist 27, hip 38.5, all EST.). '
        f'Measure the finished garment laid flat, then double for circumferences. Lengths grade ⅜ in per size unless marked held.</p>'
    )
    if len(pieces) >= 3:
        page += 1
        pom_html = ''.join(pom_table(p, st['sizes'], st['base_size']) for p in pieces[:2])
        parts.append(f'<section class="page">{hdr(st, f"{page:02d}  ·  Points of measure")}'
                     f'{pom_intro}{pom_html}{ftr(st, page, n_pages)}</section>')
        page += 1
        pom_html = ''.join(pom_table(p, st['sizes'], st['base_size']) for p in pieces[2:])
        parts.append(f'<section class="page">{hdr(st, f"{page:02d}  ·  Points of measure (cont.)")}'
                     f'<h2>POINTS OF MEASURE  ·  CONTINUED</h2>{pom_html}{ftr(st, page, n_pages)}</section>')
    else:
        page += 1
        pom_html = ''.join(pom_table(p, st['sizes'], st['base_size']) for p in pieces)
        parts.append(f'<section class="page">{hdr(st, f"{page:02d}  ·  Points of measure")}'
                     f'{pom_intro}{pom_html}{ftr(st, page, n_pages)}</section>')

    # 8 color / label / pack / sign-off
    page += 1
    color_blocks = []
    for p in pieces:
        rgb, pant, hx = colors[p['id']]
        color_blocks.append(
            f'<div class="sw"><img src="img/swatch-{p["id"]}.png" alt=""/><div>'
            f'<b>{esc(p["color_name"])}</b> — {esc(p["name"])}<div class="muted">'
            f'{esc(hx)}  ·  approx. {esc(pant)}. Photo sample only, not a lab dip.</div></div></div>'
        )
    parts.append(f'<section class="page">{hdr(st, f"{page:02d}  ·  Color, labeling, sign-off")}'
                 f'<h2>COLORWAY</h2>'
                 f'<p class="note">Colors were sampled from the reference photographs. They are approximate only. Supplier to submit a lab dip on the approved cloth, lit D65 / TL84 / incandescent, and not to approve production on the photograph alone.</p>'
                 + ''.join(color_blocks) + caveat_html
                 + f'<h2>LABELING AND PACKAGING</h2>'
                 f'<ul class="con">'
                 f'<li>Main label: Atelier 360, at CB neck or at the waist, as appropriate to the piece. EST.</li>'
                 f'<li>Care / content label: fiber, care and country of origin, to the market standard. EST.</li>'
                 f'<li>Hangtag: style {esc(st["id"])}, size, color, season {esc(st.get("season") or SEASON)}. EST.</li>'
                 f'<li>Each piece individually poly-bagged, set packed together, size sticker on the bag. EST.</li>'
                 f'</ul>'
                 f'<h2>FIT AND SIGN-OFF</h2>'
                 f'<p>{esc(st.get("fit_notes") or "")}</p>'
                 f'<p>{esc(st.get("accessories") or "")}</p>'
                 f'<table class="meta" style="margin-top:8pt">'
                 f'<tr><th>Designer</th><td></td><th>Date</th><td></td></tr>'
                 f'<tr><th>Pattern</th><td></td><th>Date</th><td></td></tr>'
                 f'<tr><th>Supplier</th><td></td><th>Date</th><td></td></tr>'
                 f'<tr><th>Fit / proto</th><td></td><th>Date</th><td></td></tr>'
                 f'</table>'
                 f'<p class="muted" style="margin-top:8pt">This document is a draft technical package for pricing and proto development. It is not a paid purchase order and not an authorization to cut a bulk run.</p>'
                 f'{ftr(st, page, n_pages)}</section>')

    parts.append('</body></html>')
    return ''.join(parts), n_pages


# ---------------------------------------------------------------------------
# Build one pack
# ---------------------------------------------------------------------------
def manifest_captions(model_id, outfit_id):
    path = REPO / 'data' / 'manifest.json'
    caps = {}
    notes = ''
    if path.is_file():
        data = json.loads(path.read_text())
        model = next((m for m in data.get('models') or [] if m.get('id') == model_id), None)
        outfit = next((o for o in (model.get('outfits') or []) if o.get('id') == outfit_id), None) if model else None
        if outfit:
            notes = outfit.get('note') or ''
            for fr in outfit.get('frames') or []:
                a = int(fr.get('angle') or 0)
                src = fr.get('source') or 'reference'
                extra = ''
                if src == 'reference-mirrored':
                    extra = f" (mirror of {fr.get('mirrorOf', '?')}°)"
                elif src == 'generated-edit':
                    extra = ' (generated edit)'
                elif src == 'reference-mirrored-edited':
                    extra = ' (mirrored edit)'
                caps[a] = f'{a:03d}°  ·  {src}{extra}'
    for a in (0, 45, 90, 135, 180, 225, 270, 315):
        caps.setdefault(a, f'{a:03d}°')
    return caps, notes


def build_pack(st, prof, out_pdf: Path, previews: Path | None, assets: Path, build_dir: Path, clean=False):
    from PIL import Image
    model_id = prof.get('modelId') or 'exact-26'
    work = build_dir
    if work.exists() and clean:
        shutil.rmtree(work)
    img_dir = work / 'img'
    work.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(exist_ok=True)
    for name, src in mt.find_fonts().items():
        dest = work / name
        if not dest.exists():
            shutil.copy(src, dest)

    frames = mt.prep_frames(assets, model_id, img_dir, outfit=st['outfit_id'])
    caps, manifest_note = manifest_captions(model_id, st['outfit_id'])
    colors = {}
    front = Image.open(frames[0])
    for p in st['pieces']:
        box = p.get('color_box') or (0.35, 0.25, 0.65, 0.45)
        rgb = sample_box(front, box)
        pant = nearest_pantone(rgb)
        colors[p['id']] = (rgb, pant, rgb_hex(rgb))
        mt.pantone_swatch(rgb, img_dir / f'swatch-{p["id"]}.png')

    # detail crops
    details = []
    def crop_frac(angle, box, dest_name, cap):
        im = Image.open(frames[angle])
        w, h = im.size
        x0, y0, x1, y1 = [int(box[0]*w), int(box[1]*h), int(box[2]*w), int(box[3]*h)]
        mt.crop_jpeg(frames[angle], (x0, y0, x1, y1), img_dir / dest_name)
        details.append((f'img/{dest_name}', cap))

    crop_frac(0, (0.30, 0.08, 0.70, 0.55), 'det-front-torso.jpg', 'Front, torso')
    crop_frac(0, (0.30, 0.40, 0.70, 0.85), 'det-front-lower.jpg', 'Front, lower')
    crop_frac(90, (0.30, 0.10, 0.70, 0.70), 'det-side.jpg', 'Side')
    crop_frac(180, (0.30, 0.08, 0.70, 0.55), 'det-back-upper.jpg', 'Back, upper')
    crop_frac(180, (0.30, 0.40, 0.70, 0.85), 'det-back-lower.jpg', 'Back, lower')
    crop_frac(45, (0.30, 0.08, 0.70, 0.70), 'det-45.jpg', 'Three-quarter, 45°')

    ctx = {
        'style': st, 'profile': prof, 'imgs': {f'view-{a:03d}': f'img/{a:03d}.jpg' for a in frames},
        'colors': colors, 'captions': caps, 'details': details, 'n_pages': 9 if len(st['pieces']) >= 3 else 8,
        'manifest_note': manifest_note,
    }
    html, n_pages = build_html(ctx)
    html_path = work / 'techpack.html'
    html_path.write_text(html)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    mt.print_pdf(html_path, out_pdf)
    print(f'Wrote {out_pdf} ({out_pdf.stat().st_size} bytes, {n_pages} pages planned)')
    if previews:
        names = ['cover', 'views', 'details', 'flats', 'bom', 'construction', 'pom']
        if len(st['pieces']) >= 3:
            names.append('pom-cont')
        names.append('color-signoff')
        written = mt.make_previews(out_pdf, Path(previews), names)
        for pth in written:
            print(f'Preview {pth}')
    return out_pdf


def _pypdf():
    """Return a python executable that can import pypdf, installing into a local venv if needed."""
    import importlib.util
    if importlib.util.find_spec('pypdf'):
        return sys.executable
    venv = Path('/tmp/pypdf-venv')
    py = venv / 'bin' / 'python'
    if not py.is_file():
        subprocess.check_call([sys.executable, '-m', 'venv', str(venv)])
        pip = venv / 'bin' / 'pip'
        subprocess.check_call([str(pip), 'install', '--upgrade', 'pip', '-q'])
        subprocess.check_call([str(pip), 'install', 'pypdf', '-q'])
    return str(py)


def merge_pdfs(paths, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    py = _pypdf()
    script = (
        'import sys\n'
        'from pypdf import PdfWriter\n'
        'w = PdfWriter()\n'
        'outs = sys.argv[1:-1]\n'
        'dest = sys.argv[-1]\n'
        'for p in outs:\n'
        '    w.append(p)\n'
        'w.write(dest)\n'
        'print(f"Wrote {dest} ({sum(1 for _ in w.pages)} pages)")\n'
    )
    subprocess.check_call([py, '-c', script, *[str(p) for p in paths], str(dest)])
    return dest


def zip_files(paths, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p, arcname=p.name)
    print(f'Wrote {dest} ({dest.stat().st_size} bytes)')
    return dest


def default_out_dir():
    return SHARED / 'techpacks' / 'model1'


def resolve_style(args):
    if getattr(args, 'style', None):
        st = style_by_id(args.style)
        if not st:
            known = ', '.join(s['id'] for s in CATALOG)
            raise SystemExit(f'Unknown style {args.style!r}. Known Model 1 styles: {known}')
        return st
    if getattr(args, 'outfit', None):
        st = style_by_outfit(args.outfit)
        if not st:
            raise SystemExit(f'No Model 1 style for outfit id {args.outfit!r}.')
        return st
    raise SystemExit('Pass --style AVA-003 (or later), --outfit <id>, or --all-model1.')


def run(args):
    if getattr(args, 'all_model1', False) or (getattr(args, 'combine', False) and not getattr(args, 'style', None) and not getattr(args, 'outfit', None)):
        return run_all_model1(args)

    if not getattr(args, 'profile', None):
        raise SystemExit('--profile is required')
    prof = mt.load_profile(args.profile)
    st = resolve_style(args)
    out_pdf = Path(args.out) if args.out else (default_out_dir() / f"{st['id']}-{st['slug']}-techpack.pdf")
    previews = Path(args.previews) if args.previews else (out_pdf.parent / 'previews' / st['id'])
    assets = Path(args.assets) if args.assets else (REPO / 'assets')
    work = Path(args.build_dir) if args.build_dir else (out_pdf.parent / '_build' / out_pdf.stem)
    return build_pack(st, prof, out_pdf, previews, assets, work, clean=getattr(args, 'clean', False))


def run_all_model1(args):
    if not getattr(args, 'profile', None):
        raise SystemExit('--profile is required')
    prof = mt.load_profile(args.profile)
    out_dir = Path(args.out) if args.out and not str(args.out).endswith('.pdf') else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = Path(args.assets) if args.assets else (REPO / 'assets')
    pdfs = []
    for st in CATALOG:
        pdf = out_dir / f"{st['id']}-{st['slug']}-techpack.pdf"
        previews = out_dir / 'previews' / st['id']
        work = out_dir / '_build' / pdf.stem
        build_pack(st, prof, pdf, previews, assets, work, clean=getattr(args, 'clean', False))
        pdfs.append(pdf)

    combined = Path(args.combine) if args.combine else (out_dir / 'model1-all-techpacks.pdf')
    merge_pdfs(pdfs, combined)
    zpath = out_dir / 'model1-all-techpacks.zip'
    zip_files(pdfs + [combined], zpath)
    # also write a small index
    index = out_dir / 'README.txt'
    lines = [
        'Model 1 (exact-26) technical packages — Atelier 360, SS27 Prototype',
        f'Date: {TODAY}',
        'Fit model: Model 1, 5 ft 6 in / 130 lb, all measures EST.',
        'Base (grey crop set) is included as AVA-003 because it is a real garment.',
        'Outfit numbers in the titles match the gallery (Outfit 1–12). USA jersey is AVA-016.',
        'Every POM, fabric, construction call and color is an estimate from the photographs.',
        '',
    ]
    for st, pdf in zip(CATALOG, pdfs):
        lines.append(f"{st['id']}  {st['outfit_label']:<12}  {st['name']}  →  {pdf.name}")
    lines += ['', f'Combined PDF: {combined.name}', f'Zip: {zpath.name}']
    index.write_text('\n'.join(lines) + '\n')
    print(f'Wrote {index}')
    return combined
