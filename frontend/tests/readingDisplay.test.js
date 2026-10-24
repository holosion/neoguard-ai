import test from 'node:test';
import assert from 'node:assert/strict';
import { latestMetricReading } from '../src/utils/readingDisplay.js';
import { vitalStatus } from '../src/utils/vitals.js';
test('partial packets preserve each recent parameter without freezing it', () => {
  const now = Date.parse('2026-10-24T18:00:10Z');
  const pulse = { recorded_at: '2026-10-24T18:00:00Z', hr: 72, spo2: 98, temp: null, quality: 'poor' };
  const temperature = { recorded_at: '2026-10-24T18:00:05Z', hr: null, spo2: null, temp: 34, quality: 'poor' };
  assert.equal(latestMetricReading([pulse, temperature], 'hr', now), pulse);
  assert.equal(latestMetricReading([pulse, temperature], 'temp', now), temperature);
  assert.equal(latestMetricReading([pulse, temperature], 'hr', now + 6000), null);
  assert.equal(latestMetricReading([], 'spo2', now), null);
});
test('bad timestamps and unavailable values never create a measurement', () => {
  const now = Date.now();
  assert.equal(latestMetricReading([{ recorded_at: 'bad', hr: 72 }], 'hr', now), null);
  assert.equal(latestMetricReading([{ recorded_at: new Date(now).toISOString(), hr: null }], 'hr', now), null);
});
test('bench limit is strictly below 32 without changing clinical thresholds', () => {
  const surface = { temp: { low: 32, surface: true } };
  assert.equal(vitalStatus('temp', 31.9, surface).ok, false);
  assert.equal(vitalStatus('temp', 32, surface).ok, true);
  assert.equal(vitalStatus('temp', 34, { temp: { low: 36.5, moderate_low: 36, severe_low: 32 } }).ok, false);
});
