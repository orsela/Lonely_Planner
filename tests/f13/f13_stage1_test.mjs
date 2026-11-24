/* Lonely Planner F13 stage 1 · dictionary completeness (Node, no browser) · version 3.0.0-alpha.18.7
   CHANGE 2026-11-24 F13-QA-06: new file (no previous version). Checks join/flow.js and invite/index.html: he and en have the same keys, every {placeholder} of the Hebrew text is in the English text,
   no English text is empty or contains Hebrew letters, and every tr('key') / J('key') used in the sources exists. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = f => readFileSync(new URL('../../' + f, import.meta.url), 'utf8');
function dict(src, start, end) {
  const i = src.indexOf(start), j = src.indexOf(end, i);
  assert.ok(i >= 0 && j > i, 'dictionary block not found: ' + start);
  return new Function('return ' + src.slice(i + start.length - 1, j + 2))();
}
const ph = s => [...String(s).matchAll(/\{([a-z]+)\}/g)].map(m => m[1]).sort().join(',');
function check(name, D, used) {
  const he = Object.keys(D.he), en = Object.keys(D.en);
  assert.deepEqual(he.filter(k => !(k in D.en)), [], name + ': keys missing in en');
  assert.deepEqual(en.filter(k => !(k in D.he)), [], name + ': keys missing in he');
  for (const k of he) {
    assert.equal(ph(D.en[k]), ph(D.he[k]), name + ': placeholders differ for ' + k);
    assert.ok(String(D.en[k]).trim().length > 0, name + ': empty en ' + k);
    assert.ok(!/[א-ת]/.test(D.en[k]), name + ': Hebrew letters in en ' + k);
    assert.ok(/[א-ת]/.test(D.he[k]) || /Google|Chrome/.test(D.he[k]), name + ': he text without Hebrew ' + k);
  }
  for (const k of used) assert.ok(k in D.he, name + ': key used in code but missing: ' + k);
}
test('join/flow.js dictionary', () => {
  const src = read('join/flow.js');
  const D = dict(src, 'const D={', '\n};\n/* tr(');
  const used = new Set([...src.matchAll(/\btr\('([A-Za-z0-9.]+)'/g)].map(m => m[1]));
  for (const m of read('app/js/f07.js').matchAll(/\bJ\('([A-Za-z0-9.]+)'/g)) used.add(m[1]);
  for (const m of src.matchAll(/ROLEK=\{[^}]*\}/g)) for (const k of m[0].matchAll(/'(r[A-Za-z]+)'/g)) used.add(k[1]);
  check('flow.js', D, used);
  assert.ok(Object.keys(D.he).length > 80);
});
test('invite/index.html dictionary', () => {
  const src = read('invite/index.html');
  const D = dict(src, 'var D={', '}};\n  var LANG_BETA');
  const used = new Set([...src.matchAll(/\btr\('([A-Za-z0-9.]+)'/g)].map(m => m[1]));
  for (const m of src.matchAll(/tr\(IS_IOS\?'(\w+)':'(\w+)'\)/g)) { used.add(m[1]); used.add(m[2]); }
  check('invite', D, used);
});
test('flags default to beta and the version is on every touched file', () => {
  for (const f of ['join/index.html', 'invite/index.html']) assert.match(read(f), /const LANG_FEATURE='beta';/, f);
  for (const f of ['join/flow.js', 'app/js/f07.js', 'join/index.html', 'invite/index.html']) assert.match(read(f), /3\.0\.0-alpha\.18\.6/, f);
});
