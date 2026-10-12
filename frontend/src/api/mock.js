// Sample data for running the front end before the backend exists.
// All patients are anonymised codes. Set VITE_USE_MOCK=false to use the real API.
const ago = (min) => new Date(Date.now() - min * 60000).toISOString();
const wait = (data, ms = 400) => new Promise((r) => setTimeout(() => r({ data: structuredClone(data) }), ms));

const patients = [
  { id: 14, patient_code: 'NB-014', risk_category: 'critical', device_code: 'DEV-001', last_reading_at: ago(2), latest_reading: { hr: 148, spo2: 89, temp: 35.8 } },
  { id: 15, patient_code: 'NB-015', risk_category: 'high', device_code: 'DEV-002', last_reading_at: ago(5), latest_reading: { hr: 132, spo2: 94, temp: 36.8 } },
  { id: 17, patient_code: 'NB-017', risk_category: 'medium', device_code: 'DEV-004', last_reading_at: ago(3), latest_reading: { hr: 128, spo2: 95, temp: 36.9 } },
  { id: 16, patient_code: 'NB-016', risk_category: 'low', device_code: 'DEV-003', last_reading_at: ago(1), latest_reading: { hr: 138, spo2: 98, temp: 37.1 } },
  { id: 9, patient_code: 'NB-009', risk_category: 'no_data', device_code: 'DEV-005', last_reading_at: ago(18), latest_reading: null },
];

const alerts = [
  { id: 1, patient_id: 14, patient_code: 'NB-014', parameter: 'spo2', severity: 'critical', message: 'SpO₂ below 90%', created_at: ago(8), acknowledged_at: null, acknowledged_by: null },
  { id: 4, patient_id: 14, patient_code: 'NB-014', parameter: 'temp', severity: 'medium', message: 'Temperature below 36.5 °C', created_at: ago(14), acknowledged_at: null, acknowledged_by: null },
  { id: 5, patient_id: 14, patient_code: 'NB-014', parameter: 'ai', severity: 'high', message: 'AI trend: falling SpO₂', created_at: ago(24), acknowledged_at: ago(21), acknowledged_by: 'Nurse A' },
  { id: 2, patient_id: 15, patient_code: 'NB-015', parameter: 'temp', severity: 'medium', message: 'Temperature below 36.5 °C', created_at: ago(20), acknowledged_at: null, acknowledged_by: null },
  { id: 3, patient_id: 16, patient_code: 'NB-016', parameter: 'ai', severity: 'high', message: 'AI trend: falling SpO₂', created_at: ago(40), acknowledged_at: null, acknowledged_by: null },
];

function readingsFor(p) {
  const r = p.latest_reading;
  if (!r) return [];
  return Array.from({ length: 30 }, (_, i) => {
    const falling = p.id === 14;
    return {
      recorded_at: ago(29 - i),
      hr: r.hr - 2 + ((i * 7) % 5),
      spo2: falling ? Math.round(94 - i * 0.17) : r.spo2,
      temp: falling ? +(37.0 - i * 0.04).toFixed(1) : r.temp,
    };
  });
}

const NOTICE = 'Synthetic research prototype; not a clinically validated risk probability.';
const risk = (p) => {
  if (p.risk_category === 'no_data') return { status: 'stale', score: null, notice: NOTICE, factors: [] };
  if (p.id === 14) {
    return { status: 'prototype', score: 0.85, category: 'high', warning: true, notice: NOTICE, factors: [
      { label: 'Temperature, trend', contribution: 1.2 },
      { label: 'SpO₂, current value', contribution: 0.9 },
      { label: 'SpO₂, trend', contribution: 0.4 },
    ] };
  }
  const score = { high: 0.62, medium: 0.4, low: 0.1 }[p.risk_category] ?? 0.1;
  return { status: 'prototype', score, category: 'low', warning: false, notice: NOTICE, factors: [] };
};

const find = (id) => patients.find((p) => p.id === Number(id)) ?? patients[0];

export const mockApi = {
  login: (username) => wait({ access_token: 'mock-token', role: username.toLowerCase().startsWith('admin') ? 'admin' : 'nurse', name: username }),
  me: () => {
    const role = localStorage.getItem('mock_role') || 'nurse';
    return wait({ username: role === 'admin' ? 'admin' : 'nurse', role }, 150);
  },
  patients: () => wait(patients),
  patient: (id) => {
    const p = find(id);
    return wait({
      ...p,
      session_started_at: ago(95),
      // Readings recorded while the device was offline and later synced.
      sync: p.id === 14 ? { recovered_count: 450, lost_count: 0, period_start: ago(55), period_end: ago(40) } : null,
    });
  },
  readings: (id) => wait(readingsFor(find(id))),
  risk: (id) => wait(risk(find(id))),
  alerts: (params = {}) => wait(alerts.filter((a) => !params.patient_id || a.patient_id === Number(params.patient_id))),
  acknowledge: (id) => {
    const a = alerts.find((x) => x.id === Number(id));
    if (a) { a.acknowledged_at = new Date().toISOString(); a.acknowledged_by = 'Nurse'; }
    return wait({ ok: true }, 250);
  },
};
