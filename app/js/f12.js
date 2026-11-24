/* Lonely Planner · F12 (shared document vault) · page side · version 3.0.0-alpha.18
   CHANGE 2026-11-24 F12-UI-01: new file (no previous version). Conversation 2 of 3 (claude/Plan_Travel_F12_spec.md §5, decisions D1-D9; server = conversation 1, docs/F12_dev_notes_server.md).
   What this file does: a "כספת משותפת" row with a counter in "עוד" (only for trips in VAULT_TRIPS), and a full-screen vault: list newest first, category filter, quota bar (warn 80 %, block 100 %),
   upload (manager / editor; pdf, jpeg, png, webp up to 10 MB; name + category), view (image inside the app, PDF through a blob and a "פתיחה" button), rename / recategorise (manager or the uploader),
   delete (manager only, through the vault-delete Edge Function). Roles are also enforced by the server (RLS + trigger); the buttons only follow them.
   NOT here (conversation 3): "save for offline" (Cache API pt-docs-v1), local cleanup after delete / member removal / device revoke, the phone check, turning the flag on.
   Everything is built with createElement/textContent. No document title is ever logged. The smart chat (F14) does not read the vault (decision D5).
   Active only when VAULT_FEATURE==='on' AND the open trip is in VAULT_TRIPS (Vietnam never is). Off / other trip / file missing: the app is exactly 3.0.0-alpha.17.1.
   Exposes only window.__ptF12 = {version, attach, mount, refresh, active, t} (t = pure helpers, also exported with module.exports for the Node tests). */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.18';
  const MAX_BYTES = 10485760, QUOTA_BYTES = 104857600, TITLE_MAX = 80;
  const TYPES = { 'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' };
  const EXT_MIME = { pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };
  const CATS = [
    { id: 'flights', label: 'טיסות', icon: '✈️' }, { id: 'lodging', label: 'לינה', icon: '🏨' },
    { id: 'insurance', label: 'ביטוח', icon: '🛡️' }, { id: 'id', label: 'זהות', icon: '🪪' }, { id: 'other', label: 'אחר', icon: '📄' }
  ];

  /* ---------- pure part ---------- */
  function catOf(id) { return CATS.filter(function (c) { return c.id === id; })[0] || CATS[CATS.length - 1]; }
  function fmtSize(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + ' B';
    if (n < 1048576) return Math.round(n / 1024) + ' KB';
    return (n / 1048576).toFixed(n >= 10485760 ? 0 : 1).replace(/\.0$/, '') + ' MB';
  }
  function extOfName(name) { const m = /\.([A-Za-z0-9]{1,5})$/.exec(String(name || '')); return m ? m[1].toLowerCase() : ''; }
  /* mime of a picked file: its own type, else (Android sometimes leaves it empty) from the extension */
  function mimeOf(f) {
    const t = String((f && f.type) || '').toLowerCase();
    if (TYPES[t]) return t;
    if (t === 'image/jpg') return 'image/jpeg';
    if (!t) return EXT_MIME[extOfName(f && f.name)] || '';
    return t;
  }
  function checkFile(f) {
    if (!f) return { ok: false, code: 'none' };
    const size = Number(f.size) || 0, mime = mimeOf(f);
    if (!TYPES[mime]) return { ok: false, code: 'type' };
    if (size <= 0) return { ok: false, code: 'empty' };
    if (size > MAX_BYTES) return { ok: false, code: 'size' };
    return { ok: true, mime: mime, ext: TYPES[mime], size: size };
  }
  function defaultTitle(name) { return String(name || '').replace(/\.[A-Za-z0-9]{1,5}$/, '').replace(/[_]+/g, ' ').trim().slice(0, TITLE_MAX); }
  function cleanTitle(s) { const v = String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); return v.length >= 1 && v.length <= TITLE_MAX ? v : null; }
  function quotaState(used, add) {
    const u = (Number(used) || 0), total = u + (Number(add) || 0), pct = Math.min(100, Math.floor(total * 100 / QUOTA_BYTES));
    return { used: u, total: total, pct: pct, level: total > QUOTA_BYTES ? 'full' : (total >= QUOTA_BYTES * 0.8 ? 'warn' : 'ok') };
  }
  /* D1 / D4: manager and editor upload; only the manager deletes; the manager or the uploader (while manager/editor) renames; viewer sees only */
  function perms(role, isUploader) {
    const up = role === 'manager' || role === 'editor';
    return { view: true, upload: up, del: role === 'manager', rename: role === 'manager' || (up && !!isUploader) };
  }
  function filterDocs(docs, cat) {
    const l = (Array.isArray(docs) ? docs : []).filter(function (d) { return !cat || cat === 'all' || d.category === cat; });
    return l.slice().sort(function (a, b) { return String(b.created_at || '').localeCompare(String(a.created_at || '')); });
  }
  function newPath(trip, docId, ext) { return trip + '/' + docId + '.' + ext; }
  function uuid() {
    try { if (root.crypto && root.crypto.randomUUID) return root.crypto.randomUUID(); } catch (e) { }
    const h = '0123456789abcdef'; let s = '';
    for (let i = 0; i < 36; i++) s += (i === 8 || i === 13 || i === 18 || i === 23) ? '-' : (i === 14 ? '4' : h[Math.floor(Math.random() * 16)]);
    return s;
  }
  /* server error → kind (docs/F12_dev_notes_server.md: 53400 quota, P0002 object problem, 23514 check, 42501 role) */
  function errKind(e) {
    const c = String((e && (e.code || e.statusCode)) || ''), m = String((e && e.message) || '').toLowerCase();
    if (c === '53400' || /quota|exceed|payload too large|too large/.test(m)) return 'quota';
    if (c === 'P0002') return 'object';
    if (c === '23514') return 'check';
    if (c === '42501' || c === '403' || /row-level security|not allowed|unauthori/.test(m)) return 'role';
    if (/network|fetch|failed to/.test(m)) return 'net';
    return 'other';
  }
  const MSG = {
    type: 'אפשר להעלות רק PDF או תמונה (JPG, PNG, WEBP).', size: 'הקובץ גדול מ-10MB.', empty: 'הקובץ ריק.', title: 'כתבו שם למסמך (עד 80 תווים).',
    quota: 'אין מספיק מקום בכספת של הטיול (100MB).', object: 'ההעלאה לא הושלמה. נסו שוב.', check: 'הקובץ לא עבר בדיקה בשרת. נסו קובץ אחר.',
    role: 'אין לכם הרשאה לפעולה הזאת.', net: 'אין חיבור. נסו שוב כשיש רשת.', other: 'משהו השתבש. נסו שוב.'
  };
  const t = { MAX_BYTES, QUOTA_BYTES, TITLE_MAX, TYPES, CATS, MSG, catOf, fmtSize, extOfName, mimeOf, checkFile, defaultTitle, cleanTitle, quotaState, perms, filterDocs, newPath, uuid, errKind };

  /* ---------- browser part ---------- */
  const B = { dep: null, trip: null, mounted: false, docs: [], used: 0, cat: 'all', loaded: false, busy: false, scr: null, obs: null };
  const CSS = '.vt-scr{position:fixed;inset:0;z-index:9000;background:var(--bg,#f6f5ef);display:flex;flex-direction:column;direction:rtl;overflow:hidden}'
    + '.vt-top{display:flex;align-items:center;gap:8px;padding:12px 12px 8px}.vt-top h2{flex:1;margin:0;font-size:1.15rem}'
    + '.vt-ib{width:44px;height:44px;min-width:44px;border-radius:12px;border:1px solid var(--border,#e2ddd0);background:#fff;color:inherit;font:inherit;font-size:1.2rem;cursor:pointer}'
    + '.vt-body{flex:1;overflow:auto;padding:0 12px 96px}'
    + '.vt-q{background:#fff;border:1px solid var(--border,#e2ddd0);border-radius:14px;padding:10px 12px;margin:4px 0 10px;font-size:.8rem}'
    + '.vt-q .vt-bar{height:8px;border-radius:99px;background:#ece8dc;overflow:hidden;margin-top:6px}.vt-q .vt-bar i{display:block;height:100%;background:#0f766e}'
    + '.vt-q.warn .vt-bar i{background:#d97706}.vt-q.full .vt-bar i{background:#b91c1c}.vt-q .vt-w{color:#b45309;margin-top:4px}.vt-q.full .vt-w{color:#b91c1c}'
    + '.vt-chips{display:flex;gap:6px;overflow-x:auto;padding:2px 0 10px}.vt-chip{flex:none;min-height:44px;padding:0 14px;border-radius:999px;border:1px solid var(--border,#e2ddd0);background:#fff;color:inherit;font:inherit;font-size:.85rem;cursor:pointer}'
    + '.vt-chip.on{background:#0f766e;border-color:#0f766e;color:#fff}'
    + '.vt-row{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--border,#e2ddd0);border-radius:14px;padding:10px 6px 10px 12px;margin-bottom:8px}'
    + '.vt-main{flex:1;min-width:0;display:flex;align-items:center;gap:10px;background:transparent;border:0;color:inherit;font:inherit;text-align:right;cursor:pointer;min-height:44px;padding:0}'
    + '.vt-ic{flex:none;width:40px;height:40px;border-radius:10px;background:#eef6f1;display:flex;align-items:center;justify-content:center;font-size:1.25rem}'
    + '.vt-tx{min-width:0}.vt-tx b{display:block;overflow-wrap:anywhere;font-size:.95rem}.vt-tx span{display:block;font-size:.72rem;opacity:.7;margin-top:2px}'
    + '.vt-empty{text-align:center;padding:40px 16px;opacity:.8}.vt-empty .vt-big{font-size:2.4rem}.vt-fab{position:absolute;left:16px;bottom:20px;min-height:52px;padding:0 20px;border-radius:999px;border:0;background:#0f766e;color:#fff;font:inherit;font-weight:700;box-shadow:0 4px 14px #0003;cursor:pointer}'
    + '.vt-ov{position:fixed;inset:0;z-index:9100;background:rgba(0,0,0,.45);display:flex;align-items:flex-end;justify-content:center;direction:rtl}'
    + '.vt-sheet{background:#fff;width:100%;max-width:520px;border-radius:16px 16px 0 0;padding:16px;max-height:88vh;overflow:auto}.vt-sheet h3{margin:0 0 10px}'
    + '.vt-sheet label{display:block;font-size:.8rem;margin:10px 0 4px}.vt-sheet input[type=text],.vt-sheet select{width:100%;min-height:44px;box-sizing:border-box;font:inherit;padding:0 10px;border:1px solid var(--border,#e2ddd0);border-radius:10px;background:#fff}'
    + '.vt-btns{display:flex;gap:8px;margin-top:14px}.vt-btn{flex:1;min-height:48px;border-radius:14px;border:1px solid var(--border,#e2ddd0);background:#fff;color:inherit;font:inherit;font-weight:700;cursor:pointer}'
    + '.vt-btn.pri{background:#0f766e;border-color:#0f766e;color:#fff}.vt-btn.dng{background:#b91c1c;border-color:#b91c1c;color:#fff}.vt-btn[disabled]{opacity:.5;cursor:default}'
    + '.vt-err{color:#b91c1c;font-size:.8rem;margin-top:8px;min-height:1em}.vt-hint{font-size:.78rem;opacity:.75;margin-top:6px}'
    + '.vt-menu button{display:flex;align-items:center;gap:10px;width:100%;min-height:48px;border:0;background:transparent;color:inherit;font:inherit;text-align:right;cursor:pointer}.vt-menu button.dng{color:#b91c1c}'
    + '.vt-view{position:fixed;inset:0;z-index:9200;background:#111318;color:#fff;display:flex;flex-direction:column;direction:rtl}.vt-view .vt-vt{display:flex;align-items:center;gap:8px;padding:12px}'
    + '.vt-view .vt-vt b{flex:1;min-width:0;overflow-wrap:anywhere}.vt-view .vt-st{flex:1;display:flex;align-items:center;justify-content:center;min-height:0;flex-direction:column;gap:14px;padding:12px;text-align:center}'
    + '.vt-view img{max-width:100%;max-height:100%;object-fit:contain}.vt-view a.vt-open{display:inline-flex;align-items:center;justify-content:center;min-height:52px;padding:0 24px;border-radius:14px;background:#0f766e;color:#fff;font-weight:700;text-decoration:none}';

  function el(tag, props, kids) {
    const e = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) { if (k === 'text') e.textContent = props[k]; else if (k === 'cls') e.className = props[k]; else e.setAttribute(k, props[k]); });
    (kids || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }
  function dep(n) { try { return B.dep && B.dep[n] ? B.dep[n]() : null; } catch (e) { return null; } }
  function online() { return typeof navigator === 'undefined' || navigator.onLine !== false; }
  function toast(m) { try { if (B.dep && B.dep.toast) B.dep.toast(m); } catch (e) { } }
  function tripId() { return dep('tripId'); }
  function active() {
    try {
      if (!B.dep || !B.dep.feature || B.dep.feature() !== 'on') return false;
      const id = tripId(), list = B.dep.trips ? B.dep.trips() : [];
      return !!id && Array.isArray(list) && list.indexOf(id) >= 0;
    } catch (e) { return false; }
  }
  function client() { return dep('client'); }
  function P(doc) { return perms(dep('role'), !!doc && doc.uploaded_by === dep('uid')); }
  function logErr(where, e) { try { console.warn('[f12] ' + where, e && (e.code || e.statusCode || e.name) || ''); } catch (x) { } }   /* codes only, never a title */

  /* ----- data ----- */
  async function load() {
    const c = client(), trip = tripId();
    if (!c || !trip || !online()) return false;
    if (B.trip !== trip) { B.trip = trip; B.docs = []; B.used = 0; B.loaded = false; }   /* another trip opened: nothing of the previous one stays */
    try {
      const q = await c.from('trip_docs').select('id,title,category,mime,size_bytes,uploaded_by,uploader_name,created_at,storage_path').eq('trip_id', trip).order('created_at', { ascending: false });
      if (q.error) throw q.error;
      B.docs = q.data || [];
      const u = await c.rpc('vault_used_bytes', { p_trip: trip });
      if (!u.error && u.data != null) B.used = Number(u.data) || 0; else B.used = B.docs.reduce(function (s, d) { return s + (Number(d.size_bytes) || 0); }, 0);
      B.loaded = true; return true;
    } catch (e) { logErr('load', e); return false; }
  }
  function summary() {
    if (!B.loaded) return 'מסמכי הטיול לכל החברים';
    return B.docs.length ? B.docs.length + ' מסמכים · ' + fmtSize(B.used) : 'עוד אין מסמכים';
  }
  function paintRow() {
    const r = document.getElementById('vaultBtn'), s = document.getElementById('vaultSummary');
    if (s) s.textContent = summary();
    return r;
  }
  async function refresh() {
    if (!active()) { const r = document.getElementById('vaultBtn'); if (r) r.remove(); return; }
    ensureRow();
    await load(); paintRow(); if (B.scr) paintScreen();
  }
  function ensureRow() {
    const more = document.getElementById('more');
    if (!more) return;
    if (!active()) { const x = document.getElementById('vaultBtn'); if (x) x.remove(); return; }
    if (document.getElementById('vaultBtn')) return;
    const anchor = document.getElementById('documentsBtn');
    const row = el('div', { cls: 'listitem', id: 'vaultBtn', role: 'button', tabindex: '0' }, [
      el('div', { cls: 'ic', style: 'background:#e6f4f1', text: '☁️' }),
      el('div', { cls: 'lbl' }, [document.createTextNode('כספת משותפת'), el('span', { cls: 'val', id: 'vaultSummary', style: 'display:block;font-weight:400;font-size:.72rem', text: summary() })]),
      el('div', { cls: 'chev', text: '‹' })
    ]);
    row.addEventListener('click', openScreen);
    row.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openScreen(); } });
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(row, anchor.nextSibling);
    else { const host = more.querySelector('div[style*="max-width"]') || more; host.insertBefore(row, host.firstChild); }
  }

  /* ----- overlays ----- */
  function sheet(title, kids) {
    const ov = el('div', { cls: 'vt-ov' }), sh = el('div', { cls: 'vt-sheet', role: 'dialog' }, [el('h3', { text: title })].concat(kids));
    ov.appendChild(sh);
    ov.addEventListener('click', function (e) { if (e.target === ov && !B.busy) ov.remove(); });
    document.body.appendChild(ov);
    return { ov: ov, sh: sh, close: function () { ov.remove(); } };
  }
  function catSelect(val) {
    const s = el('select', { id: 'vtCat' });
    CATS.forEach(function (c) { const o = el('option', { value: c.id, text: c.icon + ' ' + c.label }); if (c.id === val) o.selected = true; s.appendChild(o); });
    return s;
  }

  /* ----- main screen ----- */
  function closeScreen() { if (B.scr) { B.scr.remove(); B.scr = null; } }
  function openScreen() {
    if (!active() || B.scr) return;
    const scr = el('div', { cls: 'vt-scr', role: 'dialog', 'aria-label': 'כספת משותפת' }), back = el('button', { cls: 'vt-ib', type: 'button', 'aria-label': 'חזרה', text: '→' });
    back.addEventListener('click', closeScreen);
    scr.appendChild(el('div', { cls: 'vt-top' }, [back, el('h2', { text: 'כספת משותפת' })]));
    scr.appendChild(el('div', { cls: 'vt-body', id: 'vtBody' }));
    B.scr = scr; document.body.appendChild(scr);
    paintScreen();
    refresh();
  }
  function paintScreen() {
    const body = B.scr && B.scr.querySelector('#vtBody'); if (!body) return;
    while (body.firstChild) body.removeChild(body.firstChild);
    const old = B.scr.querySelector('.vt-fab'); if (old) old.remove();
    const q = quotaState(B.used, 0), quota = el('div', { cls: 'vt-q ' + q.level }, [
      el('div', { text: 'בשימוש ' + fmtSize(q.used) + ' מתוך 100MB' }), el('div', { cls: 'vt-bar' }, [el('i', { style: 'width:' + q.pct + '%' })])
    ]);
    if (q.level === 'warn') quota.appendChild(el('div', { cls: 'vt-w', text: 'הכספת מתמלאת. מחקו מסמכים ישנים לפני שתעלו חדשים.' }));
    if (q.level === 'full') quota.appendChild(el('div', { cls: 'vt-w', text: 'הכספת מלאה. אי אפשר להעלות עד שתמחקו מסמך.' }));
    body.appendChild(quota);
    const chips = el('div', { cls: 'vt-chips' }), all = [{ id: 'all', label: 'הכל' }].concat(CATS);
    all.forEach(function (c) {
      const b = el('button', { cls: 'vt-chip' + (B.cat === c.id ? ' on' : ''), type: 'button', text: c.label });
      b.addEventListener('click', function () { B.cat = c.id; paintScreen(); });
      chips.appendChild(b);
    });
    body.appendChild(chips);
    if (!online()) body.appendChild(el('div', { cls: 'vt-hint', text: 'אין חיבור לרשת. הכספת נפתחת רק עם חיבור (שמירה לאופליין תגיע בהמשך).' }));
    const list = filterDocs(B.docs, B.cat);
    if (!list.length) {
      body.appendChild(el('div', { cls: 'vt-empty' }, [el('div', { cls: 'vt-big', text: '🗂️' }),
        el('p', { text: B.docs.length ? 'אין מסמכים בקטגוריה הזאת.' : (B.loaded ? 'עוד לא הועלו מסמכים לטיול.' : 'טוענים…') }),
        el('p', { cls: 'vt-hint', text: B.docs.length || !B.loaded ? '' : 'כאן שומרים טיסות, ביטוח והזמנות כדי שכל החברים יוכלו לפתוח אותם.' })]));
    }
    list.forEach(function (d) { body.appendChild(rowFor(d)); });
    if (P(null).upload) {
      const fab = el('button', { cls: 'vt-fab', type: 'button', text: '＋ העלאת מסמך' });
      fab.addEventListener('click', openUpload); B.scr.appendChild(fab);
    }
  }
  function rowFor(d) {
    const c = catOf(d.category), pm = P(d);
    const main = el('button', { cls: 'vt-main', type: 'button' }, [el('div', { cls: 'vt-ic', text: d.mime === 'application/pdf' ? '📕' : c.icon }),
      el('div', { cls: 'vt-tx' }, [el('b', { text: d.title }), el('span', { text: c.label + ' · ' + fmtSize(d.size_bytes) + (d.uploader_name ? ' · ' + d.uploader_name : '') })])]);
    main.addEventListener('click', function () { openDoc(d); });
    const kids = [main];
    if (pm.rename || pm.del) {
      const more = el('button', { cls: 'vt-ib', type: 'button', 'aria-label': 'עוד פעולות', text: '⋮' });
      more.addEventListener('click', function () { openMenu(d); }); kids.push(more);
    }
    return el('div', { cls: 'vt-row' }, kids);
  }
  function openMenu(d) {
    const pm = P(d);
    const s = sheet('פעולות', []), menu = el('div', { cls: 'vt-menu' });
    if (pm.rename) { const b = el('button', { type: 'button', text: '✏️  שינוי שם וקטגוריה' }); b.addEventListener('click', function () { s.close(); openRename(d); }); menu.appendChild(b); }
    if (pm.del) { const b = el('button', { type: 'button', cls: 'dng', text: '🗑️  מחיקה' }); b.addEventListener('click', function () { s.close(); openDelete(d); }); menu.appendChild(b); }
    s.sh.appendChild(menu);
  }

  /* ----- view ----- */
  async function openDoc(d) {
    if (!online()) { toast('צריך חיבור לרשת כדי לפתוח מסמך'); return; }
    const c = client(); if (!c) return;
    const close = el('button', { cls: 'vt-ib', type: 'button', 'aria-label': 'סגירה', text: '✕', style: 'background:#2a2e38;color:#fff;border:0' });
    const stage = el('div', { cls: 'vt-st', text: 'טוענים…' }), v = el('div', { cls: 'vt-view' }, [el('div', { cls: 'vt-vt' }, [el('b', { text: d.title }), close]), stage]);
    let blobUrl = null; const end = function () { if (blobUrl) { try { URL.revokeObjectURL(blobUrl); } catch (e) { } } v.remove(); };
    close.addEventListener('click', end); document.body.appendChild(v);
    try {
      const r = await c.storage.from('trip-docs').createSignedUrl(d.storage_path, 60);
      if (r.error || !r.data || !r.data.signedUrl) throw (r.error || new Error('no url'));
      const url = r.data.signedUrl;
      stage.textContent = '';
      if (d.mime === 'application/pdf') {
        const resp = await fetch(url); if (!resp.ok) throw new Error('fetch ' + resp.status);
        const blob = await resp.blob(); blobUrl = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
        const a = el('a', { cls: 'vt-open', href: blobUrl, target: '_blank', rel: 'noopener', text: 'פתיחת ה-PDF' });
        stage.appendChild(el('div', { text: '📕' })); stage.appendChild(a);
        stage.appendChild(el('div', { cls: 'vt-hint', text: 'נפתח בצופה של המכשיר.' }));
      } else {
        const img = el('img', { alt: d.title }); img.addEventListener('error', function () { stage.textContent = 'לא הצלחנו להציג את התמונה.'; });
        img.src = url; stage.appendChild(img);
      }
    } catch (e) { logErr('open', e); stage.textContent = MSG[errKind(e)] || MSG.other; }
  }

  /* ----- upload ----- */
  function openUpload() {
    if (!P(null).upload) return;
    if (!online()) { toast(MSG.net); return; }
    const q0 = quotaState(B.used, 0); if (q0.level === 'full') { toast('הכספת מלאה. מחקו מסמך כדי להעלות.'); return; }
    const file = el('input', { type: 'file', accept: 'application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp', id: 'vtFile' });
    const title = el('input', { type: 'text', id: 'vtTitle', maxlength: String(TITLE_MAX), autocomplete: 'off' }), cat = catSelect('other');
    const err = el('div', { cls: 'vt-err', role: 'alert' }), go = el('button', { cls: 'vt-btn pri', type: 'button', text: 'העלאה' }), cancel = el('button', { cls: 'vt-btn', type: 'button', text: 'ביטול' });
    const s = sheet('העלאת מסמך', [el('label', { text: 'קובץ (PDF או תמונה, עד 10MB)' }), file, el('label', { text: 'שם להצגה' }), title, el('label', { text: 'קטגוריה' }), cat, err,
      el('div', { cls: 'vt-btns' }, [go, cancel])]);
    cancel.addEventListener('click', function () { if (!B.busy) s.close(); });
    file.addEventListener('change', function () {
      err.textContent = ''; const f = file.files && file.files[0]; if (!f) return;
      const ck = checkFile(f); if (!ck.ok) { err.textContent = MSG[ck.code] || MSG.other; file.value = ''; return; }
      if (!title.value) title.value = defaultTitle(f.name);
    });
    go.addEventListener('click', async function () {
      if (B.busy) return; err.textContent = '';
      const f = file.files && file.files[0], ck = checkFile(f);
      if (!ck.ok) { err.textContent = f ? MSG[ck.code] : 'בחרו קובץ.'; return; }
      const ttl = cleanTitle(title.value); if (!ttl) { err.textContent = MSG.title; return; }
      if (quotaState(B.used, ck.size).level === 'full') { err.textContent = MSG.quota; return; }
      if (!online()) { err.textContent = MSG.net; return; }
      B.busy = true; go.disabled = true; cancel.disabled = true; go.textContent = 'מעלים…';
      const r = await doUpload(f, ck, ttl, cat.value);
      B.busy = false;
      if (r.ok) { s.close(); toast('✅ המסמך נשמר בכספת'); await refresh(); }
      else { err.textContent = MSG[r.kind] || MSG.other; go.disabled = false; cancel.disabled = false; go.textContent = 'העלאה'; }
    });
  }
  /* contract: storage.upload (no upsert) → insert row with id = the uuid in the path → on insert failure remove the object (allowed while no row points at it) */
  async function doUpload(f, ck, ttl, category) {
    const c = client(), trip = tripId(), uid = dep('uid');
    if (!c || !trip || !uid) return { ok: false, kind: 'other' };
    const id = uuid(), path = newPath(trip, id, ck.ext), store = c.storage.from('trip-docs');
    try {
      const up = await store.upload(path, f, { contentType: ck.mime, upsert: false, cacheControl: '3600' });
      if (up.error) throw up.error;
    } catch (e) { logErr('upload', e); return { ok: false, kind: errKind(e) === 'other' ? 'object' : errKind(e) }; }
    try {
      const ins = await c.from('trip_docs').insert({ id: id, trip_id: trip, title: ttl, category: category, storage_path: path, mime: ck.mime, size_bytes: ck.size, uploaded_by: uid });
      if (ins.error) throw ins.error;
      return { ok: true, id: id };
    } catch (e) {
      logErr('insert', e);
      try { await store.remove([path]); } catch (x) { logErr('cleanup', x); }
      return { ok: false, kind: errKind(e) };
    }
  }

  /* ----- rename / delete ----- */
  function openRename(d) {
    const title = el('input', { type: 'text', id: 'vtTitle', maxlength: String(TITLE_MAX), autocomplete: 'off' }), cat = catSelect(d.category);
    title.value = d.title;
    const err = el('div', { cls: 'vt-err', role: 'alert' }), go = el('button', { cls: 'vt-btn pri', type: 'button', text: 'שמירה' }), cancel = el('button', { cls: 'vt-btn', type: 'button', text: 'ביטול' });
    const s = sheet('שינוי שם וקטגוריה', [el('label', { text: 'שם להצגה' }), title, el('label', { text: 'קטגוריה' }), cat, err, el('div', { cls: 'vt-btns' }, [go, cancel])]);
    cancel.addEventListener('click', function () { s.close(); });
    go.addEventListener('click', async function () {
      if (B.busy) return; err.textContent = '';
      const ttl = cleanTitle(title.value); if (!ttl) { err.textContent = MSG.title; return; }
      if (!online()) { err.textContent = MSG.net; return; }
      B.busy = true; go.disabled = true;
      try {
        const r = await client().from('trip_docs').update({ title: ttl, category: cat.value }).eq('id', d.id).select('id');
        if (r.error) throw r.error;
        if (!r.data || !r.data.length) throw { code: '42501' };   /* a write blocked by RLS returns 0 rows, not an error */
        B.busy = false; s.close(); toast('✅ נשמר'); await refresh();
      } catch (e) { logErr('rename', e); B.busy = false; go.disabled = false; err.textContent = MSG[errKind(e)] || MSG.other; }
    });
  }
  function openDelete(d) {
    const err = el('div', { cls: 'vt-err', role: 'alert' }), go = el('button', { cls: 'vt-btn dng', type: 'button', text: 'מחיקה' }), cancel = el('button', { cls: 'vt-btn', type: 'button', text: 'ביטול' });
    const s = sheet('למחוק את המסמך?', [el('p', { text: '"' + d.title + '" יימחק לכל חברי הטיול ולא ניתן לשחזר אותו.' }), err, el('div', { cls: 'vt-btns' }, [go, cancel])]);
    cancel.addEventListener('click', function () { if (!B.busy) s.close(); });
    go.addEventListener('click', async function () {
      if (B.busy) return; err.textContent = '';
      if (!online()) { err.textContent = MSG.net; return; }
      B.busy = true; go.disabled = true; cancel.disabled = true; go.textContent = 'מוחקים…';
      try {
        const r = await client().functions.invoke('vault-delete', { body: { doc_id: d.id } });
        if (r.error) throw r.error;
        B.busy = false; s.close(); toast('המסמך נמחק'); await refresh();
      } catch (e) { logErr('delete', e); B.busy = false; go.disabled = false; cancel.disabled = false; go.textContent = 'מחיקה'; err.textContent = MSG[errKind(e)] || MSG.other; }
    });
  }

  /* ----- wiring ----- */
  function attach(d) { B.dep = Object.assign({}, B.dep || {}, d || {}); }
  function mount(d) {
    if (typeof document === 'undefined') return false;
    B.dep = Object.assign({}, B.dep || {}, d || {});
    if (!B.dep.feature || B.dep.feature() !== 'on') return false;
    if (B.mounted) return true;
    const st = document.createElement('style'); st.id = 'ptVtCss'; st.textContent = CSS; document.head.appendChild(st);
    const more = document.getElementById('more');
    if (more && typeof MutationObserver === 'function') {
      B.obs = new MutationObserver(function () { if (more.classList.contains('active')) refresh().catch(function (e) { logErr('refresh', e); }); });
      B.obs.observe(more, { attributes: true, attributeFilter: ['class'] });
    }
    window.addEventListener('online', function () { if (B.scr) refresh().catch(function () { }); });
    window.addEventListener('offline', function () { if (B.scr) paintScreen(); });
    B.mounted = true;
    ensureRow(); if (active()) refresh().catch(function (e) { logErr('refresh', e); });
    return true;
  }

  const api = { version: VERSION, attach, mount, refresh, active, t };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.__ptF12 = api;
})(typeof window !== 'undefined' ? window : globalThis);
