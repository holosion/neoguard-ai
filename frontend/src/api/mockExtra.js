// Extra sample data for mock mode: all patients (including ones not yet monitored), sessions and attention items.
import { mockApi } from './mock';
import { mockAdminApi } from './mockAdmin';

const ago = (min) => new Date(Date.now() - min * 60000).toISOString();
const wait = (data, ms = 300) => new Promise((r) => setTimeout(() => r({ data: structuredClone(data) }), ms));

let all = null;
const ended = [{ id: 900, patient_id: 12, patient_code: 'NB-012', device_id: 4, device_code: 'DEV-004', started_at: ago(600), ended_at: ago(300), status: 'stopped' }];

async function load() {
  if (!all) {
    const base = (await mockApi.patients()).data;
    all = [
      ...base.map((p) => ({ ...p, monitored: true, session_id: p.id * 10 })),
      { id: 20, patient_code: 'NB-020', monitored: false, session_id: null, risk_category: 'no_data', device_code: '—', last_reading_at: null, latest_reading: null },
      { id: 21, patient_code: 'NB-021', monitored: false, session_id: null, risk_category: 'no_data', device_code: '—', last_reading_at: null, latest_reading: null },
    ];
  }
  return all;
}

export const mockExtra = {
  patients: async () => wait((await load()).filter((p) => p.monitored)),
  patientsAll: async () => wait(await load()),
  createPatient: async (body) => {
    (await load()).push({ id: Date.now(), patient_code: body.patient_code, monitored: false, session_id: null, risk_category: 'no_data', device_code: '—', last_reading_at: null, latest_reading: null });
    return wait({ ok: true });
  },
  sessions: async () => {
    const active = (await load()).filter((p) => p.monitored).map((p) => ({
      id: p.session_id, patient_id: p.id, patient_code: p.patient_code, device_id: null, device_code: p.device_code, started_at: ago(95), ended_at: null, status: 'active',
    }));
    return wait([...active, ...ended]);
  },
  availableDevices: async () => wait((await mockAdminApi.devices()).data.filter((d) => d.status === 'active' && !d.patient_code)),
  startSession: async ({ patient_id, device_id }) => {
    const p = (await load()).find((x) => x.id === Number(patient_id));
    const d = (await mockAdminApi.devices()).data.find((x) => x.id === Number(device_id));
    Object.assign(p, { monitored: true, session_id: Date.now(), device_code: d.device_code, risk_category: 'no_data' });
    await mockAdminApi.assign(device_id, { patient_id: -1 });
    return wait({ ok: true });
  },
  stopSession: async (sessionId) => {
    const p = (await load()).find((x) => x.session_id === Number(sessionId));
    if (p) {
      ended.unshift({ id: p.session_id, patient_id: p.id, patient_code: p.patient_code, device_id: null, device_code: p.device_code, started_at: ago(95), ended_at: new Date().toISOString(), status: 'stopped' });
      Object.assign(p, { monitored: false, session_id: null, device_code: '—' });
    }
    return wait({ ok: true });
  },
  devicesBasic: () => mockAdminApi.devices(),
  attention: async () => wait([
    { key: 'a1', text: 'NB-009 has had no readings for 18 min but its session is still open.', to: '/patients/9' },
    { key: 'a2', text: 'DEV-005 is reporting but has no patient assigned.', to: '/patients' },
  ]),
};
