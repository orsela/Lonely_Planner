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

/* ---- F12-OFF-01 (conversation 3): the offline store on a fake Cache Storage ---- */
function fakeCaches() {
  const stores = new Map();
  return { stores, async open(n) { if (!stores.has(n)) stores.set(n, new Map()); const m = stores.get(n);
    return { async match(k) { const r = m.get(k); return r ? r.clone() : undefined; }, async put(k, r) { m.set(k, r); }, async delete(k) { return m.delete(k); } }; },
    async delete(n) { return stores.delete(n); } };
}
const D = (id, extra) => Object.assign({ id, title: 'מסמך ' + id, category: 'flights', mime: 'application/pdf', size_bytes: 10, storage_path: 'T/' + id + '.pdf', created_at: '2026-11-0' + id + 'T10:00:00Z' }, extra || {});
test('F12-N11 offline store: save, open, remove; the doc cache is pt-docs-v1 and key /_vault/<trip>/<doc>', async () => {
  const cs = fakeCaches(), o = t.makeOffline(cs);
  await o.save('T', D('1'), new Blob(['hello'], { type: 'application/pdf' }));
  assert.ok(cs.stores.get('pt-docs-v1').has('/_vault/T/1'));
  assert.equal(await (await o.get('T', '1')).text(), 'hello');
  assert.deepEqual(Object.keys((await o.list('T')).saved), ['1']);
  assert.equal(await o.get('T', 'nope'), null);
  await o.remove('T', '1');
  assert.equal(cs.stores.get('pt-docs-v1').has('/_vault/T/1'), false);
  assert.deepEqual((await o.list('T')).saved, {});
});
test('F12-N12 sync (online load): a copy whose document is gone from the server is deleted; the list is kept for offline (spec criterion 8)', async () => {
  const cs = fakeCaches(), o = t.makeOffline(cs);
  await o.save('T', D('1'), new Blob(['a'])); await o.save('T', D('2'), new Blob(['b'])); await o.save('OTHER', D('1'), new Blob(['x']));
  const r = await o.sync('T', [D('2'), D('3')]);   /* 1 was deleted by the manager; 3 is new and not saved */
  assert.equal(r.removed, 1); assert.deepEqual(Object.keys(r.saved), ['2']);
  assert.equal(cs.stores.get('pt-docs-v1').has('/_vault/T/1'), false);
  assert.equal(cs.stores.get('pt-docs-v1').has('/_vault/T/2'), true);
  assert.equal(cs.stores.get('pt-docs-v1').has('/_vault/OTHER/1'), true, 'another trip is untouched');
  const l = await o.list('T'); assert.deepEqual(l.docs.map(d => d.id), ['2', '3']); assert.deepEqual(Object.keys(l.saved), ['2']);
  const e = await o.sync('T', []);   /* member removed / nothing visible any more: everything local goes */
  assert.equal(e.removed, 1); assert.equal(cs.stores.get('pt-docs-v1').has('/_vault/T/2'), false);
});
test('F12-N13 clearTrip removes one trip, clearAll removes the whole cache; both are safe when empty or without Cache API', async () => {
  const cs = fakeCaches(), o = t.makeOffline(cs);
  await o.save('T', D('1'), new Blob(['a'])); await o.save('U', D('1'), new Blob(['b']));
  await o.clearTrip('T');
  assert.equal(cs.stores.get('pt-docs-v1').has('/_vault/T/1'), false); assert.equal(cs.stores.get('pt-docs-v1').has('/_vault/U/1'), true);
  assert.deepEqual((await o.list('T')).docs, []);
  await o.clearAll(); assert.equal(cs.stores.has('pt-docs-v1'), false);
  await o.clearAll(); await o.clearTrip('nope');
  const none = t.makeOffline(undefined);
  assert.equal(none.usable, false); assert.deepEqual(await none.list('T'), { docs: [], saved: {} }); assert.equal(await none.get('T', '1'), null);
  await assert.rejects(none.save('T', D('1'), new Blob(['a'])));
});
test('F12-N14 concurrent saves do not lose index entries', async () => {
  const cs = fakeCaches(), o = t.makeOffline(cs);
  await Promise.all(['1', '2', '3', '4'].map(i => o.save('T', D(i), new Blob([i]))));
  assert.deepEqual(Object.keys((await o.list('T')).saved).sort(), ['1', '2', '3', '4']);
});
test('F12-N15 the metadata kept on the device never holds more than the listed fields', async () => {
  const cs = fakeCaches(), o = t.makeOffline(cs);
  await o.sync('T', [Object.assign(D('1'), { secret: 'x', signedUrl: 'https://s' })]);
  const j = await (await cs.stores.get('pt-docs-v1').get('/_vault/index.json')).json();
  assert.deepEqual(Object.keys(j.trips.T.docs[0]).sort(), ['category', 'created_at', 'id', 'mime', 'size_bytes', 'storage_path', 'title']);
});
