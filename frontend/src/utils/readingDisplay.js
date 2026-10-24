// Partial packets may contain only one sensor. Keep each recent bench parameter
// visible independently, and expire it instead of freezing an old pulse value.
export function latestMetricReading(readings, metric, now = Date.now(), maxAgeMs = 15000) {
  for (let i = readings.length - 1; i >= 0; i -= 1) {
    const reading = readings[i];
    const age = now - new Date(reading.recorded_at).getTime();
    if (Number.isFinite(reading[metric]) && Number.isFinite(age) && age >= -5000 && age <= maxAgeMs) return reading;
  }
  return null;
}
