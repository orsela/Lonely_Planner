// Lonely Planner NOTES-RICH Node tests · version 1.0.0
// CHANGE 2026-11-17 NOTES-RICH-T-01: new file. Pure functions of app/js/richnotes.js.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const rn = createRequire(import.meta.url)('../../app/js/richnotes.js');
const words = n => Array.from({ length: n }, (_, i) => 'מילה' + (i + 1)).join(' ');

test('AC1 bullets: newline split, markers stripped, empties dropped', () => {
  assert.deepEqual(rn.rnBullets('• א\n- ב\n\n  ג  \r\n–ד'), ['א', 'ב', 'ג', 'ד']);
  assert.deepEqual(rn.rnBullets(''), []); assert.deepEqual(rn.rnBullets(null), []);
});
test('AC2 20 words not cut; 21 cut after word 20', () => {
  assert.equal(rn.rnTrunc(words(20)).rest, '');
  const t = rn.rnTrunc(words(21));
  assert.equal(t.head.split(' ').length, 20); assert.equal(t.rest, 'מילה21');
});
test('AC3 only https becomes a link', () => {
  const t = rn.rnTokens('טיפ: https://www.romania-insider.com/brasov. ועוד http://x.org javascript:alert(1)');
  const links = t.filter(x => x.href);
  assert.equal(links.length, 1); assert.equal(links[0].label, 'romania-insider.com/brasov');
  assert.ok(t.some(x => x.t && x.t.includes('http://x.org')));
  assert.ok(!t.some(x => x.href && /^javascript/.test(x.href)));
  assert.equal(rn.rnSafeUrl('javascript:alert(1)'), null); assert.equal(rn.rnSafeUrl('http://a.b'), null); assert.equal(rn.rnSafeUrl('https://a.b/x').startsWith('https://'), true);
});
test('AC3 trailing punctuation stays outside the link', () => {
  const t = rn.rnTokens('(https://a.b/c), end');
  assert.equal(t.find(x => x.href).href, 'https://a.b/c');
});
test('AC4 images: https only, deduped, max 10', () => {
  const l = ['https://a.b/1.jpg', 'https://a.b/1.jpg', 'http://a.b/2.jpg', 'javascript:1'].concat(Array.from({ length: 15 }, (_, i) => 'https://c.d/' + i));
  const r = rn.rnImages(l); assert.equal(r.length, 10); assert.equal(r[0], 'https://a.b/1.jpg'); assert.ok(r.every(u => u.startsWith('https://')));
  assert.deepEqual(rn.rnImages(undefined), []);
  const p = rn.rnParseImageLines('https://a.b/1\nhttp://bad\n\nhttps://a.b/2'); assert.equal(p.images.length, 2); assert.equal(p.rejected, 1);
});
test('AC6 maps url with and without coordinates', () => {
  assert.equal(rn.rnMapsUrl('פלש', 'סינאיה', 45.36, 25.54), 'https://www.google.com/maps/search/?api=1&query=45.36,25.54');
  assert.equal(rn.rnMapsUrl('Peles', 'Sinaia', null, null), 'https://www.google.com/maps/search/?api=1&query=Peles%20Sinaia');
  assert.equal(rn.rnMapsUrl('Peles', '', 0, 0), 'https://www.google.com/maps/search/?api=1&query=Peles');
  assert.equal(rn.rnMapsUrl('', '', null, null), null);
});
test('inactive without a document (flag-off style)', () => { assert.equal(rn.active(), false); });
