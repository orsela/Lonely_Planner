/* Lonely Planner · BUDGET-PP – expected cost PER PERSON for each budget item, next to the actual · version 3.0.0-alpha.21.5 (BPP-FIX-01: travelers below 1 -> default 10; was alpha.17.1)
   CHANGE 2026-11-17 BUDGETPP-01: new file (no previous version). Approved by Or 2026-11-17 (mockup boards 7–8 of the NOTES-RICH canvas). The budget screen gets a card "לפי סעיף · לאדם" under the category tiles:
   one row per existing budget item (לינה, אוכל, נסיעות, שווקים וקניות, אטרקציות, אחר) with "מתוכנן לאדם" (editable by managers, in €) and "בפועל לאדם" (the item's actual spending ÷ travelers, shown in €),
   plus a ✈️ flights row (Tel Aviv – Bucharest – Tel Aviv): planned = an estimate from flight sites (with its date), actual = typed by hand after the tickets are bought (it is NOT taken from expenses).
   Data: one shared key 'planner:budget_pp' (travelers, pp{item}, flights note/actual). Until a manager saves, the Romania defaults below show (the plan's upper range; 17.11.2026 flight estimate).
   Active only when BUDGETPP_FEATURE==='on' AND the open trip is in BUDGETPP_TRIPS. Everything is built with createElement/textContent. Off / other trip / file missing: exactly 3.0.0-alpha.17. */
(function (root) {
  'use strict';
  const VERSION = '3.0.0-alpha.17.1';
  const KEY = 'planner:budget_pp';
  const ITEMS = ['lodging', 'food', 'transport', 'attractions', 'shopping', 'other'];
  const NAMES = { lodging: 'לינה', food: 'אוכל ושתייה', transport: 'נסיעות', attractions: 'אטרקציות וספא', shopping: 'שווקים וקניות', other: 'אחר', flights: 'טיסות' };
  const ICONS = { lodging: '🏨', food: '🍜', transport: '🚕', attractions: '🎟️', shopping: '🛍️', other: '💰', flights: '✈️' };
  const HINTS = { food: 'כולל בילויים', transport: 'בלי טיסות', shopping: 'לא תוכנן', flights: 'תל אביב – בוקרשט – תל אביב' };
  const DEFAULTS = { travelers: 10, pp: { lodging: 450, food: 520, transport: 280, attractions: 125, shopping: 0, other: 50, flights: 250 },
    flightsNote: 'הערכה לפי אתרי טיסות, 17.11.2026', flightsActual: null };

  /* ---------- pure part ---------- */
  function num(v, d) { const n = Number(v); return Number.isFinite(n) && n >= 0 ? n : d; }
  function bpMerge(stored) {
    const s = stored && typeof stored === 'object' ? stored : {}, pp = {};
    Object.keys(DEFAULTS.pp).forEach(function (k) { pp[k] = num(s.pp && s.pp[k], DEFAULTS.pp[k]); });
    const fa = s.flightsActual == null || s.flightsActual === '' ? null : num(s.flightsActual, null);
    /* CHANGE 2026-11-25 BPP-FIX-01: was Math.max(1, Math.round(num(s.travelers, 10))), so a stored 0 / negative became 1 traveler (and the per-person actual 10x too high);
       now a stored value below 1 is repaired to the default (10), like the other bad values (found by tests/budgetpp case 3). Saved values >= 1 are unchanged. */
    const tv = Math.round(num(s.travelers, DEFAULTS.travelers));
    return { travelers: tv >= 1 ? tv : DEFAULTS.travelers, pp: pp,
      flightsNote: typeof s.flightsNote === 'string' && s.flightsNote ? s.flightsNote : DEFAULTS.flightsNote, flightsActual: fa };
  }
  function bpTotal(plan) { return Object.keys(plan.pp).reduce(function (t, k) { return t + plan.pp[k]; }, 0); }
  /* actual group amount (home currency) → € per person; null when no rate */
  function bpPerPerson(groupHome, travelers, toEur) {
    const e = toEur ? toEur(groupHome) : groupHome; if (e == null) return null;
    return e / Math.max(1, travelers);
  }
  function bpStatus(planned, actual) { return planned > 0 && actual != null ? (actual > planned ? 'over' : 'ok') : ''; }
  function fmtEur(n) { return n == null ? '—' : '€' + Math.round(n).toLocaleString('en-US'); }

  /* ---------- browser part ---------- */
  const B = { dep: null, mounted: false };
  const CSS = '.bp-card{background:#fff;border:1px solid var(--border,#E2DDD0);border-radius:16px;padding:14px;margin:0 0 var(--sp-3,12px)}.bp-h{font-size:1rem;font-weight:700;margin:0 0 4px}.bp-sum{font-size:.8rem;color:#5B5F6B;margin:0 0 8px;line-height:1.5}'
    + '.bp-row{padding:10px 0;border-top:1px solid #EEE9DC}.bp-row:first-of-type{border-top:0}.bp-fl{background:#F1EEE4;border-radius:10px;padding:10px;margin-top:6px;border-top:0}'
    + '.bp-r1{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px}.bp-n{font-weight:700;font-size:.95rem}.bp-s{font-size:.78rem;color:#5B5F6B;line-height:1.5}'
    + '.bp-bar{height:8px;border-radius:6px;background:#E2DDD0;overflow:hidden;margin-top:6px}.bp-bar i{display:block;height:100%;background:#0F766E}.bp-bar.over i{background:#B45309}'
    + '.bp-ed{min-height:44px;min-width:44px;border:0;background:transparent;color:#0B6B63;font:inherit;font-size:.8rem;font-weight:700;cursor:pointer}'
    + '.bp-ov{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.45);display:flex;align-items:flex-end;justify-content:center}.bp-sheet{background:#fff;width:100%;max-width:520px;border-radius:16px 16px 0 0;padding:16px;direction:inherit;max-height:85vh;overflow:auto}'
    + '.bp-sheet label{display:block;font-size:.8rem;font-weight:700;color:#4A4F5C;margin:10px 0 4px}.bp-sheet input{width:100%;box-sizing:border-box;min-height:44px}.bp-btns{display:flex;gap:8px;margin-top:14px}.bp-btns .btn{flex:1}';

  function el(tag, props, kids) {
    const e = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) { if (k === 'text') e.textContent = props[k]; else if (k === 'cls') e.className = props[k]; else e.setAttribute(k, props[k]); });
    (kids || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }
  function active() {
    const d = B.dep; if (!d || typeof document === 'undefined') return false;
    try { return d.feature() === 'on' && d.trips().indexOf(d.tripId()) >= 0; } catch (e) { return false; }
  }
  function isManager() { try { return B.dep.role() === 'manager'; } catch (e) { return false; } }
  async function load() { try { const raw = await B.dep.get(KEY); return bpMerge(raw ? JSON.parse(raw) : null); } catch (e) { return bpMerge(null); } }
  async function save(plan) { plan.updatedBy = B.dep.user ? B.dep.user() : ''; plan.updatedAt = Date.now(); await B.dep.set(KEY, JSON.stringify(plan)); }

  /* actual spending per item (home currency), same rules as the budget tiles: expenses by category + booked lodging */
  async function actuals() {
    const d = B.dep, by = {}; ITEMS.forEach(function (k) { by[k] = 0; });
    (await d.expenses()).forEach(function (e) { let c = d.cat(e.category); if (!(c in by)) c = 'other'; by[c] += d.amt(e); });
    (d.days() || []).forEach(function (x) { if (x.isBooked) by.lodging += Number(x.actualCost || 0); });
    return by;
  }
  function toEurFn() {
    const home = B.dep.home();
    return function (x) { if (home === 'EUR') return x; return B.dep.conv(x, home, 'EUR'); };
  }

  function openSheet(plan, key, done) {
    const ov = el('div', { cls: 'bp-ov' }), sheet = el('div', { cls: 'bp-sheet', role: 'dialog', 'aria-modal': 'true' });
    const pIn = el('input', { type: 'number', min: '0', id: 'bpP', value: String(plan.pp[key]) }), nIn = el('input', { type: 'number', min: '1', id: 'bpN', value: String(plan.travelers) });
    sheet.appendChild(el('h3', { text: ICONS[key] + ' ' + NAMES[key] }));
    sheet.appendChild(el('label', { 'for': 'bpP', text: 'מתוכנן לאדם (€)' })); sheet.appendChild(pIn);
    let aIn = null;
    if (key === 'flights') {
      aIn = el('input', { type: 'number', min: '0', id: 'bpA', value: plan.flightsActual == null ? '' : String(plan.flightsActual), placeholder: 'עוד לא נרכש' });
      sheet.appendChild(el('label', { 'for': 'bpA', text: 'בפועל לאדם (€), מוזן ידנית אחרי רכישת הכרטיסים' })); sheet.appendChild(aIn);
    }
    sheet.appendChild(el('label', { 'for': 'bpN', text: 'מספר נוסעים לחישוב' })); sheet.appendChild(nIn);
    const ok = el('button', { type: 'button', cls: 'btn green', text: 'שמירה' }), no = el('button', { type: 'button', cls: 'btn outline', text: 'ביטול' });
    sheet.appendChild(el('div', { cls: 'bp-btns' }, [ok, no])); ov.appendChild(sheet);
    no.addEventListener('click', function () { ov.remove(); });
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
    ok.addEventListener('click', async function () {
      const p = Number(pIn.value), n = Math.round(Number(nIn.value));
      if (!(p >= 0) || !(n >= 1)) { pIn.focus(); return; }
      if (key === 'flights' && p !== plan.pp.flights) plan.flightsNote = 'עודכן ידנית ' + new Date().toLocaleDateString('he-IL');
      plan.pp[key] = p; plan.travelers = n;
      if (aIn) plan.flightsActual = aIn.value === '' ? null : Math.max(0, Number(aIn.value) || 0);
      try { await save(plan); } catch (e) { console.warn('[bp] save failed', e); }
      ov.remove(); done();
    });
    document.body.appendChild(ov); pIn.focus();
  }

  async function paint() {
    if (typeof document === 'undefined') return;
    const old = document.getElementById('bpCard'); if (old) old.remove();
    if (!active()) return;
    const anchor = document.getElementById('catChips'); if (!anchor) return;
    const plan = await load(), by = await actuals(), toEur = toEurFn(), mgr = isManager();
    const card = el('div', { id: 'bpCard', cls: 'bp-card' });
    card.appendChild(el('p', { cls: 'bp-h', text: 'לפי סעיף · לאדם' }));
    const tot = bpTotal(plan);
    card.appendChild(el('p', { cls: 'bp-sum', text: 'מתוכנן לאדם ' + fmtEur(tot) + ' · ' + plan.travelers + ' נוסעים · ' + fmtEur(tot * plan.travelers) + ' לקבוצה' }));
    ITEMS.concat(['flights']).forEach(function (k) {
      const planned = plan.pp[k]; let actualPP, actualGroup;
      if (k === 'flights') { actualPP = plan.flightsActual; actualGroup = actualPP == null ? null : actualPP * plan.travelers; }
      else { actualPP = bpPerPerson(by[k], plan.travelers, toEur); actualGroup = actualPP == null ? null : actualPP * plan.travelers; }
      const st = bpStatus(planned, actualPP);
      const row = el('div', { cls: 'bp-row' + (k === 'flights' ? ' bp-fl' : ''), 'data-bp': k });
      const r1 = el('div', { cls: 'bp-r1' }, [el('span', { cls: 'bp-n', text: ICONS[k] + ' ' + NAMES[k] + (st === 'over' ? ' ⚠️' : '') })]);
      if (mgr) { const b = el('button', { type: 'button', cls: 'bp-ed', 'aria-label': 'עריכת ' + NAMES[k], text: 'עריכה' }); b.addEventListener('click', function () { openSheet(plan, k, paint); }); r1.appendChild(b); }
      row.appendChild(r1);
      const note = k === 'flights' ? ' · ' + HINTS.flights + ' · ' + plan.flightsNote : (HINTS[k] ? ' · ' + HINTS[k] : '');
      const l1 = el('div', { cls: 'bp-s' }), b1 = el('b', { text: fmtEur(planned) });
      l1.appendChild(document.createTextNode('מתוכנן לאדם: ')); l1.appendChild(b1); l1.appendChild(document.createTextNode(note));
      row.appendChild(l1);
      const actTxt = k === 'flights' && actualPP == null ? 'בפועל לאדם: טרם נרכש' : 'בפועל לאדם: ' + fmtEur(actualPP) + ' · סה"כ לקבוצה: ' + fmtEur(actualGroup);
      row.appendChild(el('div', { cls: 'bp-s', text: actTxt }));
      const pct = planned > 0 && actualPP != null ? Math.min(100, actualPP / planned * 100) : 0;
      const bar = el('div', { cls: 'bp-bar' + (st === 'over' ? ' over' : '') }, [el('i', { style: 'width:' + pct + '%' })]); row.appendChild(bar);
      card.appendChild(row);
    });
    anchor.insertAdjacentElement('afterend', card);
  }

  function mount(dep) {
    if (typeof document === 'undefined') return false;
    B.dep = Object.assign({}, B.dep || {}, dep || {});
    if (!B.dep.feature || B.dep.feature() !== 'on') return false;
    if (B.mounted) return true;
    const st = document.createElement('style'); st.id = 'ptBpCss'; st.textContent = CSS; document.head.appendChild(st);
    B.mounted = true; return true;
  }

  const api = { version: VERSION, DEFAULTS, bpMerge, bpTotal, bpPerPerson, bpStatus, fmtEur, mount, paint, active };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.__ptBP = api;
})(typeof window !== 'undefined' ? window : globalThis);
