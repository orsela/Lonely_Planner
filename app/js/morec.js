/* MORE-COMPACT (morec.js) 1.0.0 – the compact "עוד" screen + one vault with two tabs. Mockup approved by Or 2026-11-24
   (claude/Plan_Travel_MORE-COMPACT_decisions.md). Additive: nothing existing is edited or deleted; every existing row/handler is only MOVED
   into a "הגדרות וניהול" panel or hidden by CSS, so ids, handlers and the modules that look rows up by id (f12, f13, f13tr, ...) keep working.
   Revert: MORE_LAYOUT='v1' in index.html = exactly the previous "עוד" (this file then does nothing).
   What it does:
   1. "עוד" keeps only: כספת, הזמנות וארנק, תמונות הטיול, הגדרות וניהול (+ a small "מסונכרן" line). No sub-captions, 56px rows.
   2. Every other row/section (account, language, members, translate, management, offline maps, sync card, ...) is moved, in order, into
      the panel #moreSettings. Rows that other modules add later are moved too (MutationObserver).
   3. The row "כספת" (#documentsBtn) opens the shared vault when the trip has one (#vaultBtn exists), otherwise the on-device vault as before.
      Both vault screens get the same two tabs "משותפת | במכשיר"; no tabs when the trip has no shared vault (Vietnam).
   4. Vault clean-up: category chips and the quota bar are hidden (the quota bar shows again from 80 %). */
(function (root) {
  'use strict';
  const VERSION = '1.0.0';
  const B = { mounted: false, dep: {}, flag: false };
  const d = () => root.document;
  const $ = id => d().getElementById(id);

  const CSS = [
    '.mc-on #more .listitem{min-height:56px;padding:8px 14px}',
    '.mc-on #more .listitem .val{display:none !important}',
    '.mc-on #more .listitem .lbl{font-size:1rem}',
    '.mc-badge{min-width:24px;height:24px;border-radius:12px;padding:0 7px;background:#e7f6ee;color:#0f6b4f;font-size:.75rem;font-weight:700;display:inline-flex;align-items:center;justify-content:center;margin-inline-end:6px}',
    '.mc-badge[hidden]{display:none}',
    '.mc-sync{margin:14px 0 4px;text-align:center;font-size:.75rem;font-weight:500;color:#0f6b4f}',
    '#moreSettings .mc-body{padding:0 var(--sp-3,12px) 90px;max-width:1100px;margin:auto}',
    '#moreSettings #vaultBtn{display:none}',
    '.mc-tabs{display:flex;gap:4px;padding:4px;margin:6px 0 12px;background:#e7ebe6;border-radius:13px}',
    '.mc-tabs button{flex:1;min-height:44px;border:0;border-radius:10px;background:transparent;color:#5b6472;font:inherit;font-size:.9rem;font-weight:500;cursor:pointer}',
    '.mc-tabs button[aria-selected="true"]{background:var(--primary,#0f6b4f);color:#fff;font-weight:700}',
    '.mc-on .vt-chips{display:none}',
    '.mc-on .vt-q.ok{display:none}',
    '.mc-on #documentsModal .modal-box>p.muted{display:none}',
    '.vt-scr .mc-tabs{margin:8px 14px 4px}'
  ].join('\n');

  /* ----- settings panel ----- */
  function ensurePanel() {
    let p = $('moreSettings'); if (p) return p;
    const more = $('more'); if (!more) return null;
    p = d().createElement('section'); p.id = 'moreSettings'; p.className = 'panel';
    const top = d().createElement('div'); top.className = 'topbar';
    const back = d().createElement('button'); back.className = 'topbar-back'; back.type = 'button'; back.setAttribute('aria-label', 'חזרה'); back.textContent = '›';
    back.addEventListener('click', function () { B.dep.go('more'); });
    const h = d().createElement('h1'); h.textContent = 'הגדרות וניהול';
    top.appendChild(back); top.appendChild(h);
    const body = d().createElement('div'); body.className = 'mc-body'; body.id = 'mcSettingsBody';
    p.appendChild(top); p.appendChild(body);
    more.parentNode.insertBefore(p, more.nextSibling);
    return p;
  }

  /* ----- the compact "עוד" ----- */
  const KEEP = ['documentsBtn', 'reservationsBtn', 'googlePhotosBtn', 'mcSettingsRow', 'mcSync'];
  function keep(n) { return n.nodeType !== 1 || KEEP.indexOf(n.id) >= 0 || n.classList.contains('topbar'); }
  function container() { const m = $('more'); return m && (m.querySelector('div[style*="max-width"]') || m); }

  function ensureRows() {
    const c = container(), doc = $('documentsBtn'); if (!c || !doc) return;
    const lbl = doc.querySelector('.lbl');
    if (lbl && lbl.firstChild && lbl.firstChild.nodeType === 3 && lbl.firstChild.nodeValue !== 'כספת') lbl.firstChild.nodeValue = 'כספת';
    if (!$('mcBadge')) { const b = d().createElement('span'); b.id = 'mcBadge'; b.className = 'mc-badge'; b.hidden = true; const chev = doc.querySelector('.chev'); doc.insertBefore(b, chev || null); }
    if (!$('mcSettingsRow')) {
      const r = d().createElement('div'); r.className = 'listitem'; r.id = 'mcSettingsRow'; r.setAttribute('role', 'button'); r.tabIndex = 0;
      r.innerHTML = '<div class="ic" style="background:#f1f3f0">⚙️</div><div class="lbl">הגדרות וניהול</div><div class="chev">‹</div>';
      const open = function () { B.dep.go('moreSettings'); };
      r.addEventListener('click', open);
      r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      c.appendChild(r);
    }
    if (!$('mcSync')) { const s = d().createElement('div'); s.id = 'mcSync'; s.className = 'mc-sync'; c.appendChild(s); }
    /* fixed order: vault, reservations, photos, settings, sync */
    /* only when the order is wrong: moving nodes fires the observers again (no loop) */
    const want = ['documentsBtn', 'reservationsBtn', 'googlePhotosBtn', 'mcSettingsRow', 'mcSync'].map($).filter(function (n) { return n && n.parentNode === c; });
    const have = Array.prototype.filter.call(c.children, function (n) { return want.indexOf(n) >= 0; });
    if (want.some(function (n, i) { return have[i] !== n; })) want.forEach(function (n) { c.appendChild(n); });
  }

  function sweep() {
    const more = $('more'), c = container(), p = ensurePanel(); if (!more || !c || !p) return;
    const body = $('mcSettingsBody');
    Array.prototype.slice.call(more.children).forEach(function (n) { if (n !== c && !keep(n)) body.appendChild(n); });
    Array.prototype.slice.call(c.children).forEach(function (n) { if (!keep(n)) body.appendChild(n); });
    ensureRows(); paint();
  }

  function firstInt(el) { const m = el && /\d+/.exec(el.textContent || ''); return m ? parseInt(m[0], 10) : 0; }
  function paint() {
    const b = $('mcBadge'); if (b) { const n = firstInt($('documentsSummary')) + ($('vaultBtn') ? firstInt($('vaultSummary')) : 0); if (b.textContent !== String(n)) b.textContent = n; if (b.hidden !== !n) b.hidden = !n; }
    const t = $('moreSyncTitle'), s = $('mcSync');
    if (s) { const v = t ? (/פעיל/.test(t.textContent) ? '☁️ מסונכרן' : '☁️ ' + t.textContent.trim()) : ''; if (s.textContent !== v) s.textContent = v; }
  }

  /* ----- vault tabs ----- */
  let forceLocal = false;
  function shared() { return !!$('vaultBtn'); }
  function tabs(active, host) {
    const bar = d().createElement('div'); bar.className = 'mc-tabs'; bar.setAttribute('role', 'tablist');
    [['shared', 'משותפת'], ['local', 'במכשיר']].forEach(function (t) {
      const b = d().createElement('button'); b.type = 'button'; b.setAttribute('role', 'tab'); b.textContent = t[1];
      b.setAttribute('aria-selected', t[0] === active ? 'true' : 'false');
      b.addEventListener('click', function () { if (t[0] !== active) switchTo(t[0], host); });
      bar.appendChild(b);
    });
    return bar;
  }
  function switchTo(which, host) {
    if (which === 'local') {
      const back = host.querySelector('.vt-ib'); if (back) back.click();
      forceLocal = true; try { $('documentsBtn').click(); } finally { forceLocal = false; }
      setTimeout(decorateLocal, 0);
    } else {
      const x = host.querySelector('[data-modal-x]'); if (x) x.click();
      const v = $('vaultBtn'); if (v) v.click();
    }
  }
  function decorateLocal() {
    const m = $('documentsModal'); if (!m) return;
    const box = m.querySelector('.modal-box'), head = m.querySelector('.modal-head'); if (!box || !head) return;
    const old = m.querySelector('.mc-tabs'); if (old) old.remove();
    const h = head.querySelector('h2'); if (h) h.textContent = '🔐 כספת';
    if (shared()) head.parentNode.insertBefore(tabs('local', m), head.nextSibling);
  }
  function decorateShared(scr) {
    if (!scr || scr.querySelector('.mc-tabs')) return;
    const top = scr.querySelector('.vt-top'), h = scr.querySelector('.vt-top h2'); if (!top) return;
    if (h) h.textContent = 'כספת';
    top.parentNode.insertBefore(tabs('shared', scr), top.nextSibling);
  }

  function mount(dep) {
    B.dep = Object.assign({}, B.dep, dep || {});
    if (B.mounted) return true;
    if (!B.dep.flag || B.dep.flag() !== 'compact' || typeof B.dep.go !== 'function') return false;
    const more = $('more'); if (!more) return false;
    if (B.dep.tabMap) B.dep.tabMap.moreSettings = 'more';
    const st = d().createElement('style'); st.id = 'ptMoreCCss'; st.textContent = CSS; d().head.appendChild(st);
    d().documentElement.classList.add('mc-on');
    ensurePanel(); sweep();
    /* rows other modules add later (language, translate, vault, offline maps, ...) go to the settings panel as well */
    const c = container();
    new MutationObserver(function () { sweep(); }).observe(more, { childList: true, subtree: false });
    if (c && c !== more) new MutationObserver(function () { sweep(); }).observe(c, { childList: true });
    new MutationObserver(function () { paint(); }).observe(more, { childList: true, subtree: true, characterData: true });
    new MutationObserver(function (muts) {
      muts.forEach(function (m) { Array.prototype.forEach.call(m.addedNodes, function (n) { if (n.nodeType === 1 && n.classList.contains('vt-scr')) decorateShared(n); }); });
    }).observe(d().body, { childList: true });
    /* "כספת" opens the shared vault when there is one (capture on #more: runs before the row's own handler) */
    more.addEventListener('click', function (e) {
      const row = e.target.closest && e.target.closest('#documentsBtn'); if (!row || forceLocal) return;
      if (shared()) { e.stopPropagation(); e.preventDefault(); $('vaultBtn').click(); return; }
      setTimeout(decorateLocal, 0);
    }, true);
    B.mounted = true; return true;
  }
  const api = { version: VERSION, mount: mount, sweep: sweep };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.__ptMoreC = api;
})(typeof window !== 'undefined' ? window : globalThis);
