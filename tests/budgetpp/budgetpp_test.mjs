// Lonely Planner BUDGET-PP Node tests · version 1.0.0
// CHANGE 2026-11-17 BUDGETPP-T-01: new file. Pure functions of app/js/budgetpp.js.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const bp = createRequire(import.meta.url)('../../app/js/budgetpp.js');

test('defaults: Romania plan, upper range, flights estimate; total 1675 per person', () => {
  const p = bp.bpMerge(null);
  assert.deepEqual(p.pp, { lodging: 450, food: 520, transport: 280, attractions: 125, shopping: 0, other: 50, flights: 250 });
  assert.equal(p.travelers, 10); assert.equal(bp.bpTotal(p), 1675); assert.equal(p.flightsActual, null);
});
test('without flights the total is 1425 (the plan upper range)', () => {
  const p = bp.bpMerge(null); assert.equal(bp.bpTotal(p) - p.pp.flights, 1425);
});
test('merge keeps valid saved values and repairs bad ones', () => {
  const p = bp.bpMerge({ travelers: 8, pp: { lodging: 500, food: -5, transport: 'x' }, flightsActual: 310, flightsNote: 'n' });
  assert.equal(p.pp.lodging, 500); assert.equal(p.pp.food, 520); assert.equal(p.pp.transport, 280); assert.equal(p.travelers, 8); assert.equal(p.flightsActual, 310); assert.equal(p.flightsNote, 'n');
  assert.equal(bp.bpMerge({ travelers: 0 }).travelers, 10); assert.equal(bp.bpMerge({ flightsActual: '' }).flightsActual, null);
});
test('per person actual = group ÷ travelers, in € (null without a rate)', () => {
  assert.equal(bp.bpPerPerson(4500, 10, x => x), 450);
  assert.equal(bp.bpPerPerson(4500, 10, x => x / 4), 112.5);
  assert.equal(bp.bpPerPerson(4500, 10, () => null), null);
});
test('status: over / ok / none', () => {
  assert.equal(bp.bpStatus(100, 120), 'over'); assert.equal(bp.bpStatus(100, 100), 'ok'); assert.equal(bp.bpStatus(0, 50), ''); assert.equal(bp.bpStatus(100, null), '');
});
test('inactive without a document', () => { assert.equal(bp.active(), false); });
