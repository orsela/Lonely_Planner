// Lonely Planner F12 Node tests · version 3.0.0-alpha.18
// CHANGE 2026-11-24 F12-T-01: new file (no previous version). Pure functions of app/js/f12.js (conversation 2, page side).
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const f12 = createRequire(import.meta.url)('../../app/js/f12.js');
const t = f12.t;

test('F12-N1 checkFile: type, size, empty (spec criterion 4)', () => {
  assert.equal(t.checkFile({ name: 'a.pdf', type: 'application/pdf', size: 1000 }).ext, 'pdf');
  assert.equal(t.checkFile({ name: 'a.jpeg', type: 'image/jpeg', size: 1000 }).ext, 'jpg');
  assert.equal(t.checkFile({ name: 'a.png', type: 'image/png', size: 1 }).ext, 'png');
  assert.equal(t.checkFile({ name: 'a.webp', type: 'image/webp', size: 1 }).ext, 'webp');
  assert.equal(t.checkFile({ name: 'a.pdf', type: 'application/pdf', size: 10485760 }).ok, true);
  assert.deepEqual(t.checkFile({ name: 'a.pdf', type: 'application/pdf', size: 10485761 }), { ok: false, code: 'size' });
  assert.equal(t.checkFile({ name: 'a.exe', type: 'application/x-msdownload', size: 5 }).code, 'type');
  assert.equal(t.checkFile({ name: 'a.gif', type: 'image/gif', size: 5 }).code, 'type');
  assert.equal(t.checkFile({ name: 'a.svg', type: 'image/svg+xml', size: 5 }).code, 'type');
  assert.equal(t.checkFile({ name: 'a.pdf', type: 'application/pdf', size: 0 }).code, 'empty');
  assert.equal(t.checkFile(null).code, 'none');
});
test('F12-N2 mimeOf: empty type falls back to the extension; image/jpg is fixed', () => {
  assert.equal(t.mimeOf({ name: 'Scan.JPG', type: '' }), 'image/jpeg');
  assert.equal(t.mimeOf({ name: 'x.pdf', type: '' }), 'application/pdf');
  assert.equal(t.mimeOf({ name: 'x.bin', type: '' }), '');
  assert.equal(t.mimeOf({ name: 'x', type: 'image/jpg' }), 'image/jpeg');
});
test('F12-N3 titles: default from the file name, 1-80 chars', () => {
  assert.equal(t.defaultTitle('כרטיס טיסה_TLV.pdf'), 'כרטיס טיסה TLV');
  assert.equal(t.defaultTitle('x'.repeat(200) + '.pdf').length, 80);
  assert.equal(t.cleanTitle('  שם   עם   רווחים '), 'שם עם רווחים');
  assert.equal(t.cleanTitle('   '), null); assert.equal(t.cleanTitle('x'.repeat(81)), null); assert.equal(t.cleanTitle('x'.repeat(80)).length, 80);
});
test('F12-N4 quota (D6): warn at 80 %, full above 100 MB', () => {
  assert.equal(t.quotaState(0, 0).level, 'ok');
  assert.equal(t.quotaState(83886079, 0).level, 'ok');
  assert.equal(t.quotaState(83886080, 0).level, 'warn');
  assert.equal(t.quotaState(104857600, 0).level, 'warn');
  assert.equal(t.quotaState(104857600, 1).level, 'full');
  assert.equal(t.quotaState(100000000, 10000000).level, 'full');
  assert.equal(t.quotaState(52428800, 0).pct, 50);
});
test('F12-N5 permissions (D1, D4): viewer sees only; editor uploads, never deletes; manager all', () => {
  assert.deepEqual(t.perms('viewer', true), { view: true, upload: false, del: false, rename: false });
  assert.deepEqual(t.perms('editor', false), { view: true, upload: true, del: false, rename: false });
  assert.deepEqual(t.perms('editor', true), { view: true, upload: true, del: false, rename: true });
  assert.deepEqual(t.perms('manager', false), { view: true, upload: true, del: true, rename: true });
  assert.deepEqual(t.perms(null, true), { view: true, upload: false, del: false, rename: false });
});
test('F12-N6 filterDocs: category filter, newest first', () => {
  const d = [{ id: 1, category: 'id', created_at: '2026-11-01T10:00:00Z' }, { id: 2, category: 'flights', created_at: '2026-11-03T10:00:00Z' }, { id: 3, category: 'flights', created_at: '2026-11-02T10:00:00Z' }];
  assert.deepEqual(t.filterDocs(d, 'all').map(x => x.id), [2, 3, 1]);
  assert.deepEqual(t.filterDocs(d, 'flights').map(x => x.id), [2, 3]);
  assert.deepEqual(t.filterDocs(null, 'all'), []);
});
test('F12-N7 path and uuid: <trip>/<doc>.<ext>, no file name in the path', () => {
  const id = t.uuid(); assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$|^[0-9a-f-]{36}$/);
  assert.equal(t.newPath('T', 'D', 'jpg'), 'T/D.jpg');
});
test('F12-N8 errKind maps the server codes', () => {
  assert.equal(t.errKind({ code: '53400' }), 'quota'); assert.equal(t.errKind({ code: 'P0002' }), 'object');
  assert.equal(t.errKind({ code: '23514' }), 'check'); assert.equal(t.errKind({ code: '42501' }), 'role');
  assert.equal(t.errKind({ message: 'new row violates row-level security policy' }), 'role');
  assert.equal(t.errKind({ message: 'The object exceeded the maximum allowed size' }), 'quota');
  assert.equal(t.errKind({ message: 'Failed to fetch' }), 'net'); assert.equal(t.errKind(null), 'other');
});
test('F12-N9 fmtSize and categories', () => {
  assert.equal(t.fmtSize(500), '500 B'); assert.equal(t.fmtSize(2048), '2 KB'); assert.equal(t.fmtSize(1572864), '1.5 MB'); assert.equal(t.fmtSize(10485760), '10 MB');
  assert.deepEqual(t.CATS.map(c => c.id), ['flights', 'lodging', 'insurance', 'id', 'other']); assert.equal(t.catOf('zzz').id, 'other');
});
test('F12-N10 chat stays out of the vault (D5): no trip_docs / trip-docs in chat-assistant or f14.js', async () => {
  const fs = await import('node:fs'); const r = new URL('../../', import.meta.url);
  const files = ['app/js/f14.js', 'supabase/functions/chat-assistant/index.ts'].filter(p => fs.existsSync(new URL(p, r)));
  assert.ok(files.length >= 1);
  files.forEach(p => assert.ok(!/trip_docs|trip-docs|__ptF12|vault_used_bytes/i.test(fs.readFileSync(new URL(p, r), 'utf8')), p));
});
