// Returns { ok, text } for one value. Text always states the reason, so status never depends on colour alone.
export function vitalStatus(metric, v, T) {
  if (v == null) return { ok: true, text: 'No reading' };
  if (metric === 'hr') {
    if (v < T.hr.low) return { ok: false, text: `Low, below ${T.hr.low} bpm` };
    if (v > T.hr.high) return { ok: false, text: `High, above ${T.hr.high} bpm` };
  }
  if (metric === 'spo2' && v < T.spo2.low) return { ok: false, text: `Low, below ${T.spo2.low}%` };
  if (metric === 'temp') {
    if (v < T.temp.severe_low) return { ok: false, text: 'Severely low' };
    if (v < T.temp.moderate_low) return { ok: false, text: 'Low, moderate hypothermia range' };
    if (v < T.temp.low) return { ok: false, text: `Low, below ${T.temp.low} °C` };
  }
  return { ok: true, text: 'In range' };
}

const STEP = { hr: 3, spo2: 1, temp: 0.2 };
export function trendArrow(readings, metric) {
  if (readings.length < 10) return '→ Steady';
  const diff = readings[readings.length - 1][metric] - readings[readings.length - 10][metric];
  if (diff > STEP[metric]) return '↑ Rising';
  if (diff < -STEP[metric]) return '↓ Falling';
  return '→ Steady';
}
