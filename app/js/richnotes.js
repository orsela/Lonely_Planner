/* Lonely Planner · NOTES-RICH – rich day notes, clickable links and image galleries · version 3.0.0-alpha.17
   CHANGE 2026-11-17 NOTES-RICH-01: new file (no previous version). Spec: claude/Plan_Travel_NOTES-RICH_decisions.md (mockup approved by Or 2026-11-16).
   Notes and activities of a day (and the notes of a point of interest) are drawn as bullets, one per line, a bullet over 20 words is cut after word 20 with a "+" button;
   https addresses become links (site name only); `images` (https list, max 10) on a day and on a point draw a gallery with a full-screen viewer; each point gets a "ניווט" button.
   Everything is built with createElement/textContent (no raw innerHTML). Active only when RICHNOTES_FEATURE==='on' AND the open trip is in RICHNOTES_TRIPS (Vietnam never is).
   Off / other trip / file missing: the app draws exactly as 3.0.0-alpha.16.5. The feature number is not assigned yet (file named after the feature). */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.17';
  const MAX_WORDS = 20, MAX_IMAGES = 10, GAL_SHOW = 3;

  /* ---------- pure part ---------- */
  function rnBullets(text) {
    return String(text == null ? '' : text).split(/\r?\n/)
      .map(function (l) { return l.trim().replace(/^[•·\-–*]+\s*/, '').trim(); })
      .filter(Boolean);
  }
  function rnTrunc(s, max) {
    max = max || MAX_WORDS;
    const w = String(s).trim().split(/\s+/);
    if (w.length <= max) return { head: w.join(' '), rest: '' };
    return { head: w.slice(0, max).join(' '), rest: w.slice(max).join(' ') };
  }
  function rnSafeUrl(u) {
    try { const x = new URL(String(u).trim()); return x.protocol === 'https:' && x.hostname ? x.href : null; } catch (e) { return null; }
  }
  function rnLinkLabel(href) {
    try {
      const x = new URL(href); let t = x.hostname.replace(/^www\./, '') + (x.pathname && x.pathname !== '/' ? x.pathname.replace(/\/$/, '') : '');
      return t.length > 34 ? t.slice(0, 33) + '…' : t;
    } catch (e) { return href; }
  }
  /* "text https://a.b/c, more" → [{t:'text '},{href,label},{t:', more'}] ; only https links are made */
  function rnTokens(s) {
    const out = [], re = /https:\/\/[^\s<>"']+/g; let last = 0, m;
    s = String(s);
    while ((m = re.exec(s))) {
      let raw = m[0], tail = '';
      const mt = raw.match(/[.,;:!?)\]}׳"']+$/); if (mt) { tail = mt[0]; raw = raw.slice(0, -tail.length); }
      const href = rnSafeUrl(raw);
      if (m.index > last) out.push({ t: s.slice(last, m.index) });
      if (href) out.push({ href: href, label: rnLinkLabel(href) }); else out.push({ t: raw });
      if (tail) out.push({ t: tail });
      last = m.index + m[0].length;
    }
    if (last < s.length) out.push({ t: s.slice(last) });
    return out;
  }
  function rnImages(list) {
    const seen = {}, out = [];
    (Array.isArray(list) ? list : []).forEach(function (u) {
      const h = rnSafeUrl(u); if (h && !seen[h] && out.length < MAX_IMAGES) { seen[h] = 1; out.push(h); }
    });
    return out;
  }
  function rnParseImageLines(text) {
    const lines = String(text || '').split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    const ok = rnImages(lines);
    return { images: ok, rejected: lines.length - lines.filter(function (l) { return rnSafeUrl(l); }).length };
  }
  function rnNum(v) { return v !== '' && v != null && Number.isFinite(Number(v)); }
  function rnMapsUrl(name, city, lat, lng) {
    if (rnNum(lat) && rnNum(lng) && Math.abs(Number(lat)) <= 90 && Math.abs(Number(lng)) <= 180 && !(Number(lat) === 0 && Number(lng) === 0))
      return 'https://www.google.com/maps/search/?api=1&query=' + Number(lat) + ',' + Number(lng);
    const q = [name, city].filter(Boolean).join(' ').trim();
    return q ? 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(q) : null;
  }

  /* ---------- browser part ---------- */
  const B = { dep: null, mounted: false };
  const CSS = '.rn-ul{list-style:none;margin:0;padding:0}.rn-ul li{display:flex;gap:8px;line-height:1.55;margin:0 0 4px;font-size:.95rem;color:inherit}'
    + '.rn-ul li:before{content:"•";color:#0F766E;font-weight:700;flex:none}.rn-ul li>span{min-width:0;overflow-wrap:anywhere}'
    + '.rn-ul a,.rn-wp a.rn-l{color:#0B6B63;text-decoration:underline}.rn-ul .rn-more{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;margin:-12px 0;vertical-align:middle;border:0;background:transparent;color:#0B6B63;font:inherit;font-size:1.4rem;font-weight:700;cursor:pointer}'
    + '#activities.rn-on,#notes.rn-on{display:block}'
    + '.rn-gal{display:flex;gap:8px;overflow:hidden;margin:6px 0 8px}.rn-gal button{flex:none;position:relative;width:132px;height:96px;padding:0;border:0;border-radius:12px;overflow:hidden;background:#E2DDD0;cursor:pointer}'
    + '.rn-gal img{width:100%;height:100%;object-fit:cover;display:block}.rn-gal .rn-n{display:flex;align-items:center;justify-content:center;background:#1F2430;color:#fff;font-weight:700}'
    + '.rn-wp{padding:4px 0 8px;border-bottom:1px solid var(--border,#E2DDD0)}.rn-nav{display:inline-flex;align-items:center;gap:4px;min-height:44px;padding:0 14px;border-radius:999px;border:1px solid #0F766E;color:#0B6B63;font-size:.85rem;font-weight:700;text-decoration:none}'
    + '.rn-lb{position:fixed;inset:0;z-index:100000;background:#111318;color:#fff;display:flex;flex-direction:column}.rn-lb .rn-bar{display:flex;align-items:center;justify-content:space-between;padding:16px}'
    + '.rn-lb .rn-x{width:44px;height:44px;border-radius:50%;border:0;background:#2A2E38;color:#fff;font-size:1.3rem;cursor:pointer}.rn-lb .rn-stage{flex:1;display:flex;align-items:center;justify-content:center;min-height:0}'
    + '.rn-lb img{max-width:100%;max-height:100%;object-fit:contain}'
    + '.rn-ed{margin-top:8px}.rn-ed .rn-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-top:1px solid #EEE9DC}.rn-ed .rn-u{flex:1;min-width:0;direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.8rem}'
    + '.rn-ed .rn-rm{width:44px;height:44px;border:0;background:transparent;color:#9B2C2C;font-size:1.2rem;cursor:pointer}.rn-ed .rn-add{display:flex;gap:8px;align-items:flex-start;margin-top:6px}.rn-ed .rn-add input{flex:1;direction:ltr;text-align:left}'
    + '.rn-ed .rn-err{font-size:.75rem;color:#9B2C2C;margin:4px 0 0}.rn-ov{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.45);display:flex;align-items:flex-end;justify-content:center}.rn-ov .rn-sheet{background:#fff;width:100%;max-width:520px;border-radius:16px 16px 0 0;padding:16px;max-height:85vh;overflow:auto;direction:inherit}';

  function el(tag, props, kids) {
    const e = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) { if (k === 'text') e.textContent = props[k]; else if (k === 'cls') e.className = props[k]; else e.setAttribute(k, props[k]); });
    (kids || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }
  function addRich(parent, s) {
    rnTokens(s).forEach(function (t) {
      if (t.href) { const a = el('a', { href: t.href, target: '_blank', rel: 'noopener noreferrer', text: t.label }); parent.appendChild(a); }
      else parent.appendChild(document.createTextNode(t.t));
    });
  }
  function bulletList(text) {
    const items = rnBullets(text); if (!items.length) return null;
    const ul = el('ul', { cls: 'rn-ul' });
    items.forEach(function (b) {
      const tr = rnTrunc(b), li = el('li'), sp = el('span');
      addRich(sp, tr.head);
      if (tr.rest) {
        const more = el('span'), btn = el('button', { type: 'button', cls: 'rn-more', 'aria-label': 'להמשך קריאה', 'aria-expanded': 'false', text: '+' });
        const dots = document.createTextNode('… ');
        more.style.display = 'none'; addRich(more, ' ' + tr.rest);
        sp.appendChild(dots); sp.appendChild(more); sp.appendChild(btn);
        btn.addEventListener('click', function () {
          const open = more.style.display === 'none';
          more.style.display = open ? '' : 'none'; dots.textContent = open ? ' ' : '… ';
          btn.textContent = open ? '−' : '+'; btn.setAttribute('aria-expanded', open ? 'true' : 'false');
          btn.setAttribute('aria-label', open ? 'הצגת פחות' : 'להמשך קריאה');
        });
      }
      li.appendChild(sp); ul.appendChild(li);
    });
    return ul;
  }

  function lightbox(list, start) {
    let i = start, x0 = null;
    const cnt = el('span', { text: '' }), img = el('img', { alt: '' }), stage = el('div', { cls: 'rn-stage' }, [img]);
    const close = el('button', { type: 'button', cls: 'rn-x', 'aria-label': 'סגירה', text: '✕' });
    const lb = el('div', { cls: 'rn-lb', role: 'dialog', 'aria-modal': 'true' }, [el('div', { cls: 'rn-bar' }, [cnt, close]), stage]);
    function show() { img.src = list[i]; cnt.textContent = (i + 1) + ' / ' + list.length; }
    function go(d) { i = (i + d + list.length) % list.length; show(); }
    function shut() { document.removeEventListener('keydown', key); lb.remove(); }
    function key(e) { if (e.key === 'Escape') shut(); else if (e.key === 'ArrowLeft') go(1); else if (e.key === 'ArrowRight') go(-1); }
    close.addEventListener('click', shut);
    stage.addEventListener('click', function (e) { if (e.target === stage) shut(); });
    lb.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    lb.addEventListener('touchend', function (e) { if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null; if (Math.abs(dx) > 40 && list.length > 1) go(dx < 0 ? 1 : -1); });
    img.addEventListener('error', function () { if (list.length > 1) { list.splice(i, 1); i = Math.min(i, list.length - 1); show(); } else shut(); });
    document.addEventListener('keydown', key); document.body.appendChild(lb); show();
  }
  /* day: first 3 + "+N"; point: all (max 10 → same rule, kept short) */
  function gallery(list) {
    const imgs = rnImages(list); if (!imgs.length) return null;
    const g = el('div', { cls: 'rn-gal' }); let alive = imgs.slice();
    imgs.slice(0, GAL_SHOW).forEach(function (u, k) {
      const im = el('img', { src: u, alt: '', loading: 'lazy', referrerpolicy: 'no-referrer' });
      const b = el('button', { type: 'button', 'aria-label': 'פתיחת תמונה ' + (k + 1) }, [im]);
      b.addEventListener('click', function () { lightbox(alive.slice(), Math.max(0, alive.indexOf(u))); });
      im.addEventListener('error', function () { b.remove(); alive = alive.filter(function (a) { return a !== u; }); if (!g.querySelector('button:not(.rn-n)')) g.remove(); });
      g.appendChild(b);
    });
    if (imgs.length > GAL_SHOW) {
      const n = el('button', { type: 'button', cls: 'rn-n', 'aria-label': 'עוד תמונות', text: '+' + (imgs.length - GAL_SHOW) });
      n.addEventListener('click', function () { lightbox(alive.slice(), Math.min(GAL_SHOW, alive.length - 1)); }); g.appendChild(n);
    }
    return g;
  }

  /* the images editor: rows with a remove button + an https input; get() returns the list */
  function editor(initial, onChange) {
    let cur = rnImages(initial); const box = el('div', { cls: 'rn-ed' });
    const input = el('input', { type: 'url', placeholder: 'https://…', 'aria-label': 'כתובת תמונה', inputmode: 'url' }), err = el('p', { cls: 'rn-err' });
    const add = el('button', { type: 'button', cls: 'btn green', text: 'הוספה' }), rows = el('div'), title = el('b', { text: '' });
    function draw() {
      title.textContent = 'תמונות (' + cur.length + ' מתוך ' + MAX_IMAGES + ')'; rows.textContent = '';
      cur.forEach(function (u, k) {
        const rm = el('button', { type: 'button', cls: 'rn-rm', 'aria-label': 'הסרת תמונה ' + (k + 1), text: '✕' });
        rm.addEventListener('click', function () { cur.splice(k, 1); draw(); if (onChange) onChange(); });
        rows.appendChild(el('div', { cls: 'rn-row' }, [el('span', { cls: 'rn-u', text: u }), rm]));
      });
    }
    add.addEventListener('click', function () {
      const v = input.value.trim(); err.textContent = '';
      if (!v) return;
      if (!rnSafeUrl(v)) { err.textContent = 'רק כתובות שמתחילות ב-https מתקבלות'; return; }
      if (cur.length >= MAX_IMAGES) { err.textContent = 'אפשר עד ' + MAX_IMAGES + ' תמונות'; return; }
      cur = rnImages(cur.concat([v])); input.value = ''; draw(); if (onChange) onChange();
    });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); add.click(); } });
    box.appendChild(title); box.appendChild(rows); box.appendChild(el('div', { cls: 'rn-add' }, [input, add])); box.appendChild(err); draw();
    return { el: box, get: function () { return cur.slice(); }, set: function (l) { cur = rnImages(l); draw(); } };
  }

  function active() {
    const d = B.dep; if (!d || typeof document === 'undefined') return false;
    try { return d.feature() === 'on' && d.trips().indexOf(d.tripId()) >= 0; } catch (e) { return false; }
  }
  function day() { try { return B.dep.days()[B.dep.dayIndex()]; } catch (e) { return null; } }

  function swap(id, text) {
    const t = document.getElementById(id); if (!t) return;
    const ul = bulletList(text); if (!ul) { t.classList.remove('rn-on'); return; }
    t.textContent = ''; t.classList.add('rn-on'); t.appendChild(ul);
  }
  function paintDay() {
    if (typeof document === 'undefined') return;
    ['rnDayGal'].forEach(function (id) { const o = document.getElementById(id); if (o) o.remove(); });
    Array.prototype.forEach.call(document.querySelectorAll('#waypoints .rn-wp'), function (n) { n.remove(); });
    const f = document.getElementById('rnImgEd'); if (f) f.style.display = active() ? '' : 'none';
    if (!active()) return;
    const d = day(); if (!d) return;
    swap('activities', d.activities); swap('notes', d.notes);
    const g = gallery(d.images), h = document.getElementById('title');
    if (g && h) { g.id = 'rnDayGal'; h.insertAdjacentElement('afterend', g); }
    if (B.ed) B.ed.set(d.images || []);
    const host = document.getElementById('waypoints'); if (!host) return;
    const rows = Array.prototype.filter.call(host.children, function (c) { return c.classList.contains('row'); });
    (d.waypoints || []).forEach(function (w, i) {
      const row = rows[i]; if (!row) return;
      const box = el('div', { cls: 'rn-wp' }), nb = bulletList(w.notes), pg = gallery(w.images), u = rnMapsUrl(w.name, d.region, w.lat, w.lng);
      if (nb) box.appendChild(nb); if (pg) box.appendChild(pg);
      if (u) box.appendChild(el('a', { cls: 'rn-nav', href: u, target: '_blank', rel: 'noopener noreferrer', text: '🧭 ניווט' }));
      row.insertAdjacentElement('afterend', box);
    });
  }

  /* day edit form: the images editor under the notes field; beforeSave() copies the list into the open day */
  function mountForm(form) {
    if (!form || document.getElementById('rnImgEd')) return;
    const holder = el('div', { id: 'rnImgEd' }); B.ed = editor([]); holder.appendChild(B.ed.el);
    const last = form.querySelector('#fNotes'); if (last) last.insertAdjacentElement('afterend', holder); else form.appendChild(holder);
    holder.style.display = 'none';
  }
  function beforeSave() {
    if (!active() || !B.ed) return;
    const d = day(); if (!d) return; const l = B.ed.get(); if (l.length) d.images = l; else delete d.images;
  }
  /* "🖼️ תמונות" action in a point's sheet: a small overlay with the same editor */
  function wpActions(acts, i) {
    if (!active()) return;
    const d = day(), w = d && (d.waypoints || [])[i]; if (!w) return;
    acts.unshift({ icon: '🖼️', label: 'תמונות', run: function () {
      const ed = editor(w.images || []), ov = el('div', { cls: 'rn-ov' }), save = el('button', { type: 'button', cls: 'btn green', text: 'שמירה' }), cancel = el('button', { type: 'button', cls: 'btn outline', text: 'ביטול' });
      ov.appendChild(el('div', { cls: 'rn-sheet' }, [el('h3', { text: 'תמונות · ' + (w.name || '') }), ed.el, el('div', { style: 'display:flex;gap:8px;margin-top:12px' }, [save, cancel])]));
      cancel.addEventListener('click', function () { ov.remove(); });
      save.addEventListener('click', async function () {
        const l = ed.get(); if (l.length) w.images = l; else delete w.images;
        try { if (B.dep.save) await B.dep.save(); if (B.dep.render) B.dep.render(); } catch (e) { console.warn('[rn] save failed', e); }
        ov.remove();
      });
      document.body.appendChild(ov);
    } });
  }

  function mount(dep) {
    if (typeof document === 'undefined') return false;
    B.dep = Object.assign({}, B.dep || {}, dep || {});
    if (!B.dep.feature || B.dep.feature() !== 'on') return false;
    if (B.mounted) return true;
    const st = document.createElement('style'); st.id = 'ptRnCss'; st.textContent = CSS; document.head.appendChild(st);
    try { mountForm(B.dep.form && B.dep.form()); } catch (e) { console.warn('[rn] form', e); }
    B.mounted = true; return true;
  }

  const api = { version: VERSION, rnBullets, rnTrunc, rnSafeUrl, rnLinkLabel, rnTokens, rnImages, rnParseImageLines, rnMapsUrl, mount, paintDay, beforeSave, wpActions, active };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.__ptRN = api;
})(typeof window !== 'undefined' ? window : globalThis);
