// Purchase-order enquiry builder for Avata (model gallery). Drafts only — never sends.
(function () {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ico = (d, size = 18) =>
    `<svg class="ms-i" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  const I = {
    back: ico('<path d="M15 5l-7 7 7 7"/>'),
    list: ico('<path d="M8 7h12M8 12h12M8 17h12"/><circle cx="4.5" cy="7" r="1.1" fill="currentColor" stroke="none"/><circle cx="4.5" cy="12" r="1.1" fill="currentColor" stroke="none"/><circle cx="4.5" cy="17" r="1.1" fill="currentColor" stroke="none"/>', 22),
    down: ico('<path d="M12 4v12M7 11l5 5 5-5"/>'),
    mail: ico('<path d="M4 7h16v10H4z"/><path d="M4 7l8 6 8-6"/>'),
    copy: ico('<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6A1.5 1.5 0 0014 4.5H6A1.5 1.5 0 004.5 6v8A1.5 1.5 0 006 15.5h2.5"/>'),
  };

  const STORAGE_KEY = 'avata-po-draft';
  const STYLES_URL = 'data/styles.json';
  const FALLBACK_STYLES = [
    { id: 'AVA-002', name: 'Slim 5-Pocket Chino', kind: 'chino', techpack: 'AVA-002 Slim 5-Pocket Chino technical package', season: 'SS27 Prototype', sizes: ['28','29','30','31','32','33','34','36'], sizePrefix: 'W', sizeLabel: 'US waist', baseSize: '31', colors: ['Mid Grey'], defaultColor: 'Mid Grey', fitModel: '5 ft 6 in / 130 lb slim male (Model 6). Base size W31, outseam 35 in.', units: 'in' },
    { id: 'AVA-001', name: 'Tank & Short Set', kind: 'set', techpack: 'AVA-001 Tank & Short Set technical package', season: 'SS27 Prototype', sizes: ['XS','S','M','L','XL'], sizePrefix: '', sizeLabel: 'US size', baseSize: 'L', colors: ['Black'], defaultColor: 'Black', fitModel: 'Gallery Model 2, US 12–14 / L. First proto in size L.', units: 'in' },
  ];

  let styles = FALLBACK_STYLES.slice();
  let form = defaultForm();
  let root, openFlag = false, onClose = null, lastFocus = null;
  let stylesLoaded = false;

  function defaultForm() {
    return {
      styleId: 'AVA-002',
      color: 'Mid Grey',
      qtys: {},
      ship: '',
      notes: '',
      fitSample: true,
      poNumber: defaultPoNumber(),
    };
  }
  function defaultPoNumber() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `AVA-PO-${y}${m}${day}-001`;
  }
  function styleById(id) { return styles.find(s => s.id === id) || styles[0]; }
  function sizeKey(st, sz) { return (st.sizePrefix || '') + sz; }
  function qtyOf(st, sz) { const n = Number(form.qtys[sizeKey(st, sz)]); return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0; }
  function bulkTotal(st) { return (st.sizes || []).reduce((a, sz) => a + qtyOf(st, sz), 0); }
  function sampleQty(st) { return form.fitSample ? 1 : 0; }
  function grandTotal(st) { return bulkTotal(st) + sampleQty(st); }

  function loadDraft() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const d = JSON.parse(raw);
      form = { ...defaultForm(), ...d, qtys: { ...(d.qtys || {}) } };
    } catch (_) {}
  }
  function saveDraft() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(form)); } catch (_) {}
  }

  function toast(msg) {
    let host = $('#msToasts');
    if (!host) { host = document.createElement('div'); host.id = 'msToasts'; document.body.append(host); }
    const t = document.createElement('div');
    t.className = 'ms-toast'; t.setAttribute('role', 'status'); t.textContent = msg;
    host.append(t); setTimeout(() => t.remove(), 3600);
  }

  function downloadBlob(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  function todayISO() {
    const d = new Date();
    const z = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}`;
  }
  function prettyDate(iso) {
    if (!iso) return 'To be confirmed';
    const [y, m, d] = iso.split('-').map(Number);
    if (!y) return iso;
    const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    return `${d} ${months[m-1]} ${y}`;
  }

  function lines(st) {
    return (st.sizes || []).map(sz => ({ size: sizeKey(st, sz), qty: qtyOf(st, sz) })).filter(x => x.qty > 0);
  }

  function emailDraft(st) {
    const ls = lines(st);
    const qtyBlock = ls.length
      ? ls.map(x => `  ${x.size}  —  ${x.qty}`).join('\n')
      : '  (no bulk quantities entered)';
    const sample = form.fitSample
      ? `\nPlease also cut one fit sample in the base size (${sizeKey(st, st.baseSize)}) of this pattern, per supplier, before the bulk cut.\n`
      : '';
    const notes = (form.notes || '').trim();
    return (
`Subject: Purchase order enquiry — ${st.id} ${st.name} — Atelier 360

Hello,

Please find a purchase-order enquiry from Atelier 360 for style ${st.id}, ${st.name}, colorway ${form.color || st.defaultColor}, referencing the ${st.techpack}.

Draft PO number: ${form.poNumber}
Season: ${st.season || 'SS27 Prototype'}
Quantities (${st.sizeLabel || 'size'}):
${qtyBlock}
Bulk units: ${bulkTotal(st)}
${sample}
Target ship date: ${prettyDate(form.ship)}
${notes ? 'Notes: ' + notes + '\n' : ''}
This is a draft enquiry for pricing, lead time and confirmation. It is not a paid purchase order and not an authorization to cut a bulk production run or to charge a card. Please confirm unit price, lead time, and proto / fit-sample availability against the technical package.

Thank you,
Jordan Salazar
Atelier 360`
    );
  }

  function mailtoHref(st) {
    const raw = emailDraft(st);
    const sub = raw.split('\n')[0].replace(/^Subject:\s*/, '');
    const body = raw.split('\n').slice(2).join('\n').replace(/^\n/, '');
    return 'mailto:?subject=' + encodeURIComponent(sub) + '&body=' + encodeURIComponent(body);
  }

  function csvText(st) {
    const rows = [['po_number','style','style_name','color','size','qty','kind','ship_date','fit_sample','notes','status']];
    const notes = (form.notes || '').replace(/\s+/g, ' ').trim();
    lines(st).forEach(x => {
      rows.push([form.poNumber, st.id, st.name, form.color, x.size, x.qty, 'bulk', form.ship || '', form.fitSample ? 'yes' : 'no', notes, 'DRAFT enquiry']);
    });
    if (form.fitSample) {
      rows.push([form.poNumber, st.id, st.name, form.color, sizeKey(st, st.baseSize), 1, 'fit-sample', form.ship || '', 'yes', notes, 'DRAFT enquiry']);
    }
    const escCell = c => {
      const t = String(c ?? '');
      return /[",\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
    };
    return rows.map(r => r.map(escCell).join(',')).join('\n') + '\n';
  }

  function poHtml(st) {
    const ls = lines(st);
    const qtyRows = (st.sizes || []).map(sz => {
      const k = sizeKey(st, sz);
      const q = qtyOf(st, sz);
      const base = String(sz) === String(st.baseSize) ? ' class="base"' : '';
      return `<tr${base}><td>${esc(k)}${String(sz) === String(st.baseSize) ? ' <span class="muted">(base)</span>' : ''}</td><td class="r">${q ? q : '—'}</td></tr>`;
    }).join('');
    return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${esc(form.poNumber)} — Draft PO enquiry</title>
<style>
  :root{--ink:#161616;--muted:#5c5c57;--rule:#d0cec8;--est:#7a3f0c;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:-apple-system,BlinkMacSystemFont,Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff;padding:0.6in;font-size:10.5pt;line-height:1.4;}
  h1{font-family:Georgia,Times,serif;font-size:22pt;margin:0 0 4pt;}
  h2{font-size:10pt;letter-spacing:.08em;border-bottom:1.2pt solid var(--ink);padding-bottom:3pt;margin:16pt 0 8pt;}
  .kicker{letter-spacing:.16em;font-size:8.5pt;font-weight:700;color:var(--est);}
  .row{display:flex;justify-content:space-between;gap:16pt;border-bottom:1pt solid var(--ink);padding-bottom:10pt;margin-bottom:12pt;}
  table{width:100%;border-collapse:collapse;font-size:10pt;margin:6pt 0 10pt;}
  th,td{border:0.5pt solid #c8c6c0;padding:5pt 8pt;text-align:left;}
  th{background:#f3f2ee;letter-spacing:.04em;font-size:8.5pt;}
  td.r,th.r{text-align:right;}
  tr.base td{background:#ebeae5;font-weight:700;}
  .muted{color:var(--muted);font-weight:400;}
  .disclaimer{margin-top:14pt;border:0.8pt solid var(--est);color:var(--est);padding:8pt 10pt;font-size:9pt;}
  .meta td,.meta th{border:none;border-bottom:0.4pt solid var(--rule);background:none;padding:4pt 8pt 4pt 0;}
  .meta th{width:1.6in;color:var(--muted);letter-spacing:.06em;font-size:8pt;text-transform:uppercase;}
  @media print{body{padding:0.4in} .noprint{display:none!important}}
</style></head><body>
  <div class="row">
    <div>
      <div style="font-weight:700;letter-spacing:.2em;font-size:10pt;">ATELIER 360</div>
      <div class="muted" style="font-size:8.5pt;margin-top:2pt;">APPAREL  ·  PURCHASE ORDER ENQUIRY</div>
    </div>
    <div style="text-align:right;">
      <div class="kicker">DRAFT  ·  NOT A PAID ORDER</div>
      <div style="font-weight:700;font-size:14pt;margin-top:2pt;">${esc(form.poNumber)}</div>
      <div class="muted" style="font-size:9pt;">${esc(prettyDate(todayISO()))}</div>
    </div>
  </div>
  <h1>${esc(st.name)}</h1>
  <p class="muted">${esc(st.id)}  ·  ${esc(st.season || '')}  ·  Colorway ${esc(form.color)}</p>
  <table class="meta">
    <tr><th>Supplier</th><td>To be confirmed</td></tr>
    <tr><th>Tech pack</th><td>${esc(st.techpack)}</td></tr>
    <tr><th>Fit / base size</th><td>${esc(st.fitModel)} Base ${esc(sizeKey(st, st.baseSize))}.</td></tr>
    <tr><th>Target ship date</th><td>${esc(prettyDate(form.ship))}</td></tr>
    <tr><th>Buyer</th><td>Jordan Salazar, Atelier 360</td></tr>
  </table>
  <h2>QUANTITIES  ·  ${esc(st.sizeLabel || 'Size')}</h2>
  <table>
    <tr><th>Size</th><th class="r">Units</th></tr>
    ${qtyRows}
    <tr><td>Bulk total</td><td class="r">${bulkTotal(st)}</td></tr>
    ${form.fitSample ? `<tr><td>Fit sample, base size ${esc(sizeKey(st, st.baseSize))} (one per supplier, before bulk)</td><td class="r">1</td></tr>` : ''}
    <tr class="base"><td>Total units to discuss</td><td class="r">${grandTotal(st)}</td></tr>
  </table>
  ${form.notes ? `<h2>NOTES</h2><p>${esc(form.notes)}</p>` : ''}
  <div class="disclaimer"><b>DRAFT ENQUIRY ONLY.</b> This document is for pricing, lead time and confirmation against the referenced technical package. It is not a paid purchase order, not a contract, and not an authorization to cut a bulk production run or to charge a card. Confirm unit price, lead time and proto / fit-sample availability in writing before any cut.</div>
</body></html>`;
  }

  function isOrderHash() {
    return location.hash.replace(/^#/, '').split('/')[0] === 'order';
  }
  function orderView() {
    let el = $('#orderView');
    if (!el) { el = document.createElement('div'); el.id = 'orderView'; el.hidden = true; document.body.append(el); }
    return el;
  }

  function mountEntry(panel) {
    if (!panel) return;
    let el = $('#orderEntry');
    if (!el) {
      el = document.createElement('a');
      el.id = 'orderEntry';
      el.className = 'ms-entry';
      el.href = '#order';
      const after = $('#measureEntry');
      if (after && after.parentNode === panel) panel.insertBefore(el, after.nextSibling);
      else {
        const h2 = panel.querySelector('h2');
        panel.insertBefore(el, h2 || panel.firstChild);
      }
      el.addEventListener('click', ev => { ev.preventDefault(); open(); });
    }
    refreshEntry();
  }
  function refreshEntry() {
    const el = $('#orderEntry');
    if (!el) return;
    const st = styleById(form.styleId);
    const t = grandTotal(st);
    const b = bulkTotal(st);
    const sub = b ? `${st.id} · ${t} unit${t === 1 ? '' : 's'} in draft` : 'Draft a supplier enquiry — nothing is sent';
    el.innerHTML = `${I.list}<span class="ms-entry-copy"><small>Order</small><b>Purchase order</b><em>${esc(sub)}</em></span><span class="pill">Open</span>`;
  }

  function renderOrder(v) {
    const st = styleById(form.styleId);
    if (!form.color) form.color = st.defaultColor || (st.colors && st.colors[0]) || '';
    const styleOpts = styles.map(s => `<option value="${esc(s.id)}" ${s.id === st.id ? 'selected' : ''}>${esc(s.id)} — ${esc(s.name)}</option>`).join('');
    const colorOpts = (st.colors || []).map(c => `<option value="${esc(c)}" ${c === form.color ? 'selected' : ''}>${esc(c)}</option>`).join('');
    const extraColor = (st.colors || []).includes(form.color) ? '' : `<option value="${esc(form.color)}" selected>${esc(form.color)}</option>`;
    const sizeGrid = (st.sizes || []).map(sz => {
      const k = sizeKey(st, sz);
      const q = form.qtys[k] || '';
      const base = String(sz) === String(st.baseSize) ? ' <span class="n">base</span>' : '';
      return `<label class="ms-field po-sz"><span>${esc(k)}${base}</span><input type="number" inputmode="numeric" min="0" step="1" data-sz="${esc(k)}" value="${esc(q)}" placeholder="0" aria-label="Quantity, size ${esc(k)}"></label>`;
    }).join('');

    v.innerHTML = `<div class="ms-bar">
        <button type="button" class="pill" id="poBack">${I.back}<span>Models</span></button>
      </div>
      <h1 class="ms-title">Purchase <em>order</em></h1>
      <p class="ms-lede">Draft a supplier enquiry from a tech pack. US sizes. Nothing is sent or charged — you download a summary or copy an email draft, or open it in your own mail app.</p>

      <section class="ms-box">
        <label class="ms-field"><span>Style / tech pack</span>
          <select id="poStyle">${styleOpts}</select></label>
        <p class="ms-how" id="poTech">${esc(st.techpack)}. ${esc(st.fitModel)}</p>
        <label class="ms-field"><span>Colorway</span>
          <select id="poColor">${colorOpts}${extraColor}</select></label>
        <label class="ms-field"><span>Or type a color</span>
          <input type="text" id="poColorText" value="${esc(form.color)}" maxlength="60" autocomplete="off"></label>
        <label class="ms-field"><span>Target ship date</span>
          <input type="date" id="poShip" value="${esc(form.ship)}"></label>
        <label class="ms-field"><span>Draft PO number</span>
          <input type="text" id="poNum" value="${esc(form.poNumber)}" maxlength="40"></label>
        <label class="ms-field"><span>Notes</span>
          <textarea id="poNotes" rows="3" maxlength="800" placeholder="Lead time, fabric, labeling…">${esc(form.notes)}</textarea></label>
      </section>

      <p class="ms-kicker">Quantity per size <span>${esc(st.sizeLabel || 'size')}</span></p>
      <section class="ms-box">
        <div class="po-sizes">${sizeGrid}</div>
        <label class="po-check"><input type="checkbox" id="poSample" ${form.fitSample ? 'checked' : ''}>
          <span>Include one fit sample in the base size (${esc(sizeKey(st, st.baseSize))}) per supplier, before the bulk cut. Recommended.</span></label>
        <p class="po-total" id="poTotal"></p>
      </section>

      <div class="ms-actions" style="margin-bottom:10px;flex-wrap:wrap">
        <button type="button" class="pill" id="poCsv">${I.down}<span>Download CSV</span></button>
        <button type="button" class="pill" id="poPrint">${I.down}<span>Print / save PO</span></button>
      </div>
      <div class="ms-actions" style="margin-bottom:18px;flex-wrap:wrap">
        <button type="button" class="pill" id="poCopy">${I.copy}<span>Copy email draft</span></button>
        <a class="pill" id="poMail" href="#">${I.mail}<span>Open in mail app</span></a>
      </div>
      <p class="ms-how" style="margin-bottom:24px">The mail button only opens your mail app with the draft filled in. This site never sends the message.</p>`;

    bindOrder(v);
    refreshTotals(v);
  }

  function readForm(v) {
    const st = styleById($('#poStyle', v).value);
    form.styleId = st.id;
    form.color = ($('#poColorText', v).value || $('#poColor', v).value || st.defaultColor || '').trim();
    form.ship = $('#poShip', v).value;
    form.notes = $('#poNotes', v).value;
    form.poNumber = ($('#poNum', v).value || '').trim() || defaultPoNumber();
    form.fitSample = $('#poSample', v).checked;
    form.qtys = form.qtys || {};
    v.querySelectorAll('[data-sz]').forEach(inp => {
      const k = inp.dataset.sz;
      const n = inp.value === '' ? 0 : Number(inp.value);
      if (Number.isFinite(n) && n > 0) form.qtys[k] = Math.floor(n);
      else delete form.qtys[k];
    });
    saveDraft();
    return st;
  }

  function refreshTotals(v) {
    const st = styleById(form.styleId);
    const b = bulkTotal(st), s = sampleQty(st), g = b + s;
    const el = $('#poTotal', v);
    if (el) el.innerHTML = s
      ? `<b>${g}</b> units in this draft <span class="muted">(${b} bulk + 1 fit sample)</span>`
      : `<b>${g}</b> unit${g === 1 ? '' : 's'} in this draft`;
    const mail = $('#poMail', v);
    if (mail) mail.href = mailtoHref(st);
    refreshEntry();
  }

  function bindOrder(v) {
    $('#poBack', v).onclick = () => close();
    const onChange = () => { readForm(v); refreshTotals(v); };
    ['poStyle','poColor','poColorText','poShip','poNotes','poNum','poSample'].forEach(id => {
      const el = $('#' + id, v);
      if (!el) return;
      el.addEventListener('input', onChange);
      el.addEventListener('change', () => {
        if (id === 'poStyle') {
          readForm(v);
          const st = styleById(form.styleId);
          if (st.defaultColor) form.color = st.defaultColor;
          saveDraft();
          renderOrder(v);
        } else if (id === 'poColor') {
          $('#poColorText', v).value = $('#poColor', v).value;
          onChange();
        } else onChange();
      });
    });
    v.querySelectorAll('[data-sz]').forEach(inp => inp.addEventListener('input', onChange));

    $('#poCsv', v).onclick = () => {
      const st = readForm(v);
      if (!grandTotal(st)) { toast('Enter a quantity, or keep the fit-sample box checked.'); return; }
      downloadBlob(new Blob([csvText(st)], { type: 'text/csv' }), `${form.poNumber}.csv`);
      toast('CSV saved.');
    };
    $('#poPrint', v).onclick = () => {
      const st = readForm(v);
      if (!grandTotal(st)) { toast('Enter a quantity, or keep the fit-sample box checked.'); return; }
      const w = window.open('', '_blank');
      if (!w) { toast('Allow pop-ups to print or save the PO.'); return; }
      w.document.write(poHtml(st));
      w.document.close();
      w.focus();
      setTimeout(() => { try { w.print(); } catch (_) {} }, 250);
    };
    $('#poCopy', v).onclick = async () => {
      const st = readForm(v);
      const text = emailDraft(st);
      try {
        await navigator.clipboard.writeText(text);
        toast('Email draft copied. Nothing was sent.');
      } catch (_) {
        toast('Could not copy — select the draft from Open in mail app instead.');
      }
    };
    $('#poMail', v).addEventListener('click', ev => {
      const st = readForm(v);
      ev.currentTarget.href = mailtoHref(st);
      // Let the browser open the mail app; do not send anything ourselves.
    });
  }

  async function ensureStyles() {
    if (stylesLoaded) return;
    try {
      const res = await fetch(STYLES_URL, { cache: 'no-cache' });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.styles) && data.styles.length) styles = data.styles;
      }
    } catch (_) {}
    stylesLoaded = true;
  }

  async function open(opts = {}) {
    if (window.Measure && Measure.isOpen()) Measure.close({ fromHash: true });
    await ensureStyles();
    loadDraft();
    root = orderView();
    if (!openFlag) lastFocus = document.activeElement;
    openFlag = true;
    document.body.classList.add('order-open');
    const toasts = $('#msToasts');
    if (toasts) toasts.replaceChildren();
    root.hidden = false;
    renderOrder(root);
    if (!opts.fromHash && !isOrderHash()) history.pushState(null, '', '#order');
    window.scrollTo(0, 0);
    $('#poBack', root)?.focus();
  }
  function close(opts = {}) {
    if (!openFlag) return;
    openFlag = false;
    document.body.classList.remove('order-open');
    const el = $('#orderView');
    if (el) el.hidden = true;
    refreshEntry();
    if (!opts.fromHash && isOrderHash()) {
      if (typeof onClose === 'function') onClose();
      else history.back();
    }
    if (lastFocus && lastFocus.focus) try { lastFocus.focus(); } catch (_) {}
  }
  function bind(opts = {}) { if (opts.onClose) onClose = opts.onClose; }

  window.addEventListener('popstate', () => {
    if (isOrderHash()) open({ fromHash: true });
    else if (openFlag) close({ fromHash: true });
  });
  window.addEventListener('hashchange', () => {
    if (isOrderHash()) { if (!openFlag) open({ fromHash: true }); }
    else if (openFlag) close({ fromHash: true });
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && openFlag && !(e.target.closest && e.target.closest('input,textarea,select'))) {
      e.preventDefault(); close();
    }
  });

  window.Order = {
    mountEntry, open, close, isOpen: () => openFlag, isOrderHash, bind,
    emailDraft, csvText, poHtml, styleById,
  };
})();
