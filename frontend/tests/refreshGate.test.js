import test from 'node:test';
import assert from 'node:assert/strict';
import { RefreshGate } from '../src/utils/refreshGate.js';

test('slow requests are not overlapped by faster polling ticks', () => {
  const gate = new RefreshGate();
  const first = gate.start();
  assert.ok(first);
  assert.equal(gate.start(), null);
  assert.equal(gate.isCurrent(first), true);
  gate.finish(first);
  assert.ok(gate.start());
});

test('an old patient response cannot update or release a new patient request', () => {
  const gate = new RefreshGate();
  const oldPatient = gate.start();
  gate.invalidate();
  const newPatient = gate.start();
  assert.equal(gate.isCurrent(oldPatient), false);
  gate.finish(oldPatient);
  assert.equal(gate.isCurrent(newPatient), true);
  assert.equal(gate.start(), null);
  gate.finish(newPatient);
  assert.ok(gate.start());
});
