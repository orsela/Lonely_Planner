/* Lonely Planner F13 · generator of app/css/f13-ltr.css · version 3.0.0-alpha.18.7
   CHANGE 2026-11-24 F13-GEN-01: new file (no previous version). Stage 3 of claude/Plan_Travel_F13_spec.md §8: the app was written right-to-left with physical CSS
   (text-align, left/right, margin/padding/border -left/-right, float, translateX). In English (<html dir="ltr">) those rules must mirror. This script reads every CSS rule
   of app/index.html (<style> blocks and CSS inside JS strings) and app/js/*.js and writes, for each rule that has physical-direction declarations, the mirrored declarations
   under `html[dir=ltr] <selector>` (with !important, so a more specific original cannot win). Nothing is emitted for rules that centre with left/right:50% + translateX(-50%),
   for symmetric pairs (left:0;right:0) or for direction:ltr blocks (URL / number fields: they are already left-to-right). Inline style="text-align:…" is mirrored by attribute selectors.
   Not mirrored on purpose (stage 4): gradient/background directions, arrow glyphs inside Hebrew strings (the English catalog picks the arrow), rotate().
   Usage: node tests/f13/gen_ltr.mjs          → writes app/css/f13-ltr.css
          node tests/f13/gen_ltr.mjs --check  → exits 1 when the committed file is stale (tests/f13/f13_stage3_test.mjs runs this in memory) */
import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const VERSION = '3.0.0-alpha.18.7';

function splitDecls(body) {
  const out = []; let cur = '', depth = 0, q = '';
  for (const ch of body) {
    if (q) { cur += ch; if (ch === q) q = ''; continue; }
    if (ch === '"' || ch === "'") { q = ch; cur += ch; continue; }
    if (ch === '(') depth++; if (ch === ')') depth = Math.max(0, depth - 1);
    if (ch === ';' && depth === 0) { out.push(cur); cur = ''; } else cur += ch;
  }
  if (cur.trim()) out.push(cur);
  return out.map(d => { const i = d.indexOf(':'); return i < 0 ? null : [d.slice(0, i).trim().toLowerCase(), d.slice(i + 1).replace(/!important/i, '').trim()]; }).filter(Boolean);
}
function parseCss(css, wrap = '') {
  css = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const rules = []; let i = 0;
  while (i < css.length) {
    const open = css.indexOf('{', i); if (open < 0) break;
    const prelude = css.slice(i, open).trim();
    let depth = 1, j = open + 1;
    while (j < css.length && depth) { if (css[j] === '{') depth++; else if (css[j] === '}') depth--; j++; }
    const body = css.slice(open + 1, j - 1);
    if (prelude.startsWith('@')) {
      if (/^@(media|supports|layer)/i.test(prelude)) rules.push(...parseCss(body, wrap + prelude + '\u0001'));
    } else if (prelude && !/[;"`]/.test(prelude) && !/\bvar\s|function|=>/.test(prelude)) {
      rules.push({ wrap, sel: prelude.replace(/\s+/g, ' '), decls: splitDecls(body) });
    }
    i = j;
  }
  return rules;
}
const flipSide = s => s.replace(/left|right/g, m => (m === 'left' ? 'right' : 'left'));
function four(v) {                     // margin/padding shorthand with 4 values: swap 2nd and 4th
  const p = v.split(/\s+(?![^(]*\))/); if (p.length !== 4 || p[1] === p[3]) return null;
  return [p[0], p[3], p[2], p[1]].join(' ');
}
export function mirror(decls) {
  const m = new Map(decls); const out = []; const has = k => m.has(k);
  const isLtrBlock = /ltr/.test(m.get('direction') || '');
  const centred = /50%/.test((m.get('left') || '') + (m.get('right') || '')) || /translateX\(\s*-?50%/.test(m.get('transform') || '');
  const ta = (m.get('text-align') || '').trim();
  if (ta === 'right') out.push(['text-align', 'left']); else if (ta === 'left' && !isLtrBlock) out.push(['text-align', 'right']);
  const fl = (m.get('float') || '').trim(); if (fl === 'left' || fl === 'right') out.push(['float', flipSide(fl)]);
  if (!centred && !isLtrBlock && (has('left') || has('right'))) {
    const L = m.get('left'), R = m.get('right');
    if (L !== R) { out.push(['left', R === undefined ? 'auto' : R]); out.push(['right', L === undefined ? 'auto' : L]); }
  }
  for (const base of ['margin', 'padding']) {
    const L = m.get(base + '-left'), R = m.get(base + '-right');
    if (L !== R) { if (R !== undefined) out.push([base + '-left', R]); if (L !== undefined) out.push([base + '-right', L]); }   // only the sides the rule sets: the other side keeps its base value
    const sh = m.get(base); if (sh && !isLtrBlock) { const f = four(sh); if (f) out.push([base, f]); }
  }
  for (const [k, v] of m) {
    let r;
    if ((r = /^border-(left|right)(-.*)?$/.exec(k)) && !/radius/.test(k)) out.push([flipSide(k), v]);
    else if (/^border-(top|bottom)-(left|right)-radius$/.test(k)) out.push([flipSide(k), v]);
    else if (k === 'transform' && !centred && /translateX\(/.test(v)) {
      const nv = v.replace(/translateX\(\s*(-?)([^)]+)\)/g, (a, s, n) => 'translateX(' + (s ? '' : '-') + n + ')');
      if (nv !== v) out.push(['transform', nv]);
    }
  }
  // de-duplicate (keep the last value of a property)
  const seen = new Map(); for (const [k, v] of out) seen.set(k, v);
  return [...seen];
}
function prefix(sel) {
  return sel.split(',').map(s => s.trim()).filter(Boolean).map(s => {
    if (/^html\b/.test(s)) return s.replace(/^html/, 'html[dir=ltr]');
    if (/^:root\b/.test(s)) return s.replace(/^:root/, 'html[dir=ltr]');
    return 'html[dir=ltr] ' + s;
  }).join(',');
}
function cssSources() {
  const files = [join(REPO, 'app/index.html'), ...readdirSync(join(REPO, 'app/js')).filter(f => f.endsWith('.js') && f !== 'f13.js').sort().map(f => join(REPO, 'app/js', f))];
  const chunks = [];
  for (const f of files) {
    const t = readFileSync(f, 'utf8'), name = f.slice(REPO.length + 1);
    if (f.endsWith('.html')) for (const m of t.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) chunks.push([name, m[1]]);
    for (const m of t.matchAll(/`((?:[^`\\]|\\[\s\S])*)`/g)) {
      const s = m[1].replace(/\$\{[^}]*\}/g, '0');
      if (/\{[^{}]*\b(left|right|text-align|float|translateX)\b[^{}]*\}/.test(s) && /[.#\w\]\)]\s*\{/.test(s) && !/<\/?[a-z]/i.test(s.slice(0, 40))) chunks.push([name, s]);
    }
  }
  return chunks;
}
export function build() {
  const out = []; const seen = new Set(); let n = 0;
  for (const [name, css] of cssSources()) {
    for (const r of parseCss(css)) {
      const d = mirror(r.decls); if (!d.length) continue;
      const body = d.map(([k, v]) => k + ':' + v + '!important').join(';');
      const rule = prefix(r.sel) + '{' + body + '}';
      const wrapped = r.wrap ? r.wrap.split('\u0001').filter(Boolean).map(w => w + '{').join('') + rule + '}'.repeat(r.wrap.split('\u0001').filter(Boolean).length) : rule;
      const key = name + '|' + wrapped; if (seen.has(key)) continue; seen.add(key); out.push(wrapped); n++;
    }
  }
  const inline = [
    'html[dir=ltr] [style*="text-align:right"]:not([style*="direction:ltr"]),html[dir=ltr] [style*="text-align: right"]:not([style*="direction:ltr"]){text-align:left!important}',
    'html[dir=ltr] [style*="text-align:left"]:not([style*="direction:ltr"]),html[dir=ltr] [style*="text-align: left"]:not([style*="direction:ltr"]){text-align:right!important}',
    'html[dir=ltr] .pt-ltr{text-align:left!important}'
  ];
  const head = '/* Lonely Planner · F13 stage 3 · mirrored physical CSS for <html dir="ltr"> · version ' + VERSION + ' · GENERATED by tests/f13/gen_ltr.mjs — do not edit by hand (' + n + ' rules)\n' +
    '   CHANGE 2026-11-24 F13-CSS-01: new file (no previous version). Loaded by app/js/f13.js only while the document is English/LTR; Hebrew never loads it. Re-run the generator after any CSS change (tests/f13/f13_stage3_test.mjs fails when this file is stale). */\n';
  return head + out.concat(inline).join('\n') + '\n';
}
if (process.argv[1] && process.argv[1].endsWith('gen_ltr.mjs')) {
  const file = join(REPO, 'app/css/f13-ltr.css'), css = build();
  if (process.argv.includes('--check')) { let cur = ''; try { cur = readFileSync(file, 'utf8'); } catch (e) {} if (cur !== css) { console.error('app/css/f13-ltr.css is stale'); process.exit(1); } console.log('fresh'); }
  else { mkdirSync(dirname(file), { recursive: true }); writeFileSync(file, css); console.log('wrote', file, css.split('\n').length - 3, 'rules'); }
}
