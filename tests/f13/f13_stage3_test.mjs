/* Lonely Planner F13 stage 3 · the mirrored CSS generator (Node, no browser) · version 3.0.0-alpha.18.7
   CHANGE 2026-11-24 F13-QA-09: new file (no previous version). The committed app/css/f13-ltr.css must be exactly what tests/f13/gen_ltr.mjs produces from the current CSS (a stale file fails here),
   and mirror() keeps its rules: text-align / left-right / padding / transform flip; centring (left:50% + translateX), symmetric pairs and direction:ltr blocks are left alone. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build, mirror } from './gen_ltr.mjs';
const css = readFileSync(new URL('../../app/css/f13-ltr.css', import.meta.url), 'utf8');
const M = s => Object.fromEntries(mirror(s.split(';').map(d => d.split(':').map(x => x.trim()))));

test('the committed css is fresh (run: node tests/f13/gen_ltr.mjs)', () => { assert.equal(css, build()); });
test('text-align, positions, padding, transform mirror', () => {
  assert.deepEqual(M('text-align:right'), { 'text-align': 'left' });
  assert.deepEqual(M('position:absolute;right:18px'), { left: '18px', right: 'auto' });
  assert.deepEqual(M('left:10px;right:4px'), { left: '4px', right: '10px' });
  assert.deepEqual(M('padding-right:28px'), { 'padding-left': '28px' });
  assert.deepEqual(M('padding:5px 8px 5px 11px'), { padding: '5px 11px 5px 8px' });
  assert.deepEqual(M('transform:translateX(12px)'), { transform: 'translateX(-12px)' });
  assert.deepEqual(M('border-right:2px solid #000'), { 'border-left': '2px solid #000' });
});
test('centring, symmetric pairs and ltr blocks stay', () => {
  assert.deepEqual(M('left:50%;transform:translateX(-50%)'), {});
  assert.deepEqual(M('left:0;right:0'), {});
  assert.deepEqual(M('padding:0 14px'), {});
  assert.deepEqual(M('direction:ltr;text-align:left'), {});
  assert.deepEqual(M('direction:ltr;text-align:right'), { 'text-align': 'left' });
});
test('no rule leaks outside html[dir=ltr] and the file has the real rules', () => {
  const rules = css.split('\n').filter(l => l && !l.startsWith('/*') && !l.startsWith('   CHANGE'));
  assert.ok(rules.length > 50);
  for (const r of rules) assert.ok(/^(@[a-z]+[^{]*\{)?html\[dir=ltr\]/.test(r), 'unprefixed: ' + r.slice(0, 80));
  assert.match(css, /\.topbar \.topbar-back\{left:18px!important;right:auto!important\}/);
});
