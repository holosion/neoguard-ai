// Sample admin data for mock mode. Patient codes only, no real names.
import { mockApi } from './mock';

const ago = (min) => new Date(Date.now() - min * 60000).toISOString();
const wait = (data, ms = 350) => new Promise((r) => setTimeout(() => r({ data: structuredClone(data) }), ms));

const devices = [
  { id: 1, device_code: 'DEV-001', name: 'Ward A', location: 'Neonatal ward', status: 'active', patient_code: 'NB-014', health: 'ok', last_seen_at: ago(1), battery: 85, wifi_dbm: -70, storage_pct: 41, issue: null },
  { id: 2, device_code: 'DEV-002', name: 'Ward B', location: 'Neonatal ward', status: 'active', patient_code: 'NB-015', health: 'fail', last_seen_at: ago(240), battery: 12, wifi_dbm: -85, storage_pct: 38, issue: 'RTC error' },
  { id: 3, device_code: 'DEV-003', name: 'Ward C', location: 'Maternity ward', status: 'active', patient_code: 'NB-016', health: 'warn', last_seen_at: ago(1), battery: 60, wifi_dbm: -72, storage_pct: 92, issue: 'LCD timeout; storage nearly full' },
  { id: 4, device_code: 'DEV-004', name: 'Ward A', location: 'Neonatal ward', status: 'active', patient_code: 'NB-017', health: 'ok', last_seen_at: ago(3), battery: 77, wifi_dbm: -66, storage_pct: 30, issue: null },
  { id: 5, device_code: 'DEV-005', name: 'Ward B', location: 'Neonatal ward', status: 'active', patient_code: null, health: 'ok', last_seen_at: ago(2), battery: 90, wifi_dbm: -64, storage_pct: 22, issue: null, sending_without_patient: true },
  { id: 6, device_code: 'DEV-006', name: 'Spare', location: 'Store', status: 'inactive', patient_code: null, health: 'ok', last_seen_at: ago(2880), battery: 100, wifi_dbm: null, storage_pct: 5, issue: null },
];
const unassignedPatients = [{ id: 20, patient_code: 'NB-020' }, { id: 21, patient_code: 'NB-021' }];
const users = [
  { id: 101, username: 'sample.nurse.a', role: 'nurse', email: 'nurse.a@example.org', status: 'pending', created_at: ago(120) },
  { id: 102, username: 'sample.officer.b', role: 'clinician', email: 'officer.b@example.org', status: 'pending', created_at: ago(1000) },
  { id: 1, username: 'nurse', role: 'nurse', email: 'nurse@example.org', status: 'active', created_at: ago(20000) },
  { id: 2, username: 'admin', role: 'admin', email: 'admin@example.org', status: 'active', created_at: ago(30000) },
];

const minsAgo = (iso) => Math.round((Date.now() - new Date(iso).getTime()) / 60000);
const find = (id) => devices.find((d) => d.id === Number(id));

function series(from, to, n = 13) {
  return Array.from({ length: n }, (_, i) => ({ t: Date.now() - (n - 1 - i) * 2 * 3600000, v: Math.round(from + ((to - from) * i) / (n - 1)) }));
}

function components(d) {
  const failRtc = d.id === 2;
  return [
    { name: 'RTC (DS3231)', status: failRtc ? 'fail' : 'ok', detail: failRtc ? 'Clock drift 15 s' : 'Clock in sync', interface: 'I²C 0x68', critical: true },
    { name: 'LCD', status: d.id === 2 || d.id === 3 ? 'warn' : 'ok', detail: d.id === 3 ? 'Display timeout' : d.id === 2 ? 'Backlight dim' : 'Working', interface: 'I²C 0x27', critical: false },
    { name: 'MAX30102', status: 'ok', detail: 'Working', interface: 'I²C 0x57', critical: true },
    { name: 'DS18B20', status: 'ok', detail: 'Working', interface: 'GPIO 4', critical: true },
    { name: 'Buzzer', status: 'ok', detail: 'Working', interface: 'GPIO 23', critical: true },
    { name: 'Storage (microSD)', status: d.storage_pct >= 90 ? 'warn' : 'ok', detail: `${d.storage_pct}% used${d.storage_pct >= 90 ? '. Sync soon so no readings are lost' : ''}`, interface: 'SPI', critical: false },
  ];
}

export const mockAdminApi = {
  overview: async () => {
    const active = devices.filter((d) => d.status === 'active');
    const alerts = (await mockApi.alerts()).data;
    const attention = [];
    active.forEach((d) => {
      if (d.sending_without_patient) attention.push({ id: d.id, text: `${d.device_code} is sending readings but has no patient assigned. Its alerts still appear in the alert log.` });
      if (d.patient_code && minsAgo(d.last_seen_at) > 30) attention.push({ id: d.id, text: `${d.device_code} has sent no readings for ${minsAgo(d.last_seen_at)} min but the session for ${d.patient_code} is still open.` });
      if (d.storage_pct >= 90) attention.push({ id: d.id, text: `${d.device_code} storage is ${d.storage_pct}% full. Reconnect it so its saved readings can sync.` });
    });
    return wait({
      devices_online: active.filter((d) => minsAgo(d.last_seen_at) <= 10).length,
      devices_total: active.length,
      active_sessions: active.filter((d) => d.patient_code).length,
      critical_alerts: alerts.filter((a) => a.severity === 'critical').length,
      unacknowledged_critical: alerts.filter((a) => a.severity === 'critical' && !a.acknowledged_at).length,
      sync_lag_min: 0,
      pending_users: users.filter((u) => u.status === 'pending').length,
      attention,
      device_health: active,
      recent_alerts: alerts.filter((a) => a.severity === 'critical'),
    });
  },
  devices: () => wait(devices),
  device: (id) => {
    const d = find(id);
    return wait({ ...d, components: components(d), telemetry: { battery: series(100, d.battery), wifi: series(-50, d.wifi_dbm ?? -50) } });
  },
  registerDevice: (body) => {
    devices.push({ id: Date.now(), status: 'inactive', patient_code: null, health: 'ok', last_seen_at: null, battery: null, wifi_dbm: null, storage_pct: 0, issue: null, ...body });
    return wait({ ok: true, device_secret: 'mock-secret-0000-do-not-use' });
  },
  updateDevice: (id, body) => { Object.assign(find(id), body); return wait({ ok: true }); },
  decommission: (id) => { Object.assign(find(id), { status: 'retired', patient_code: null }); return wait({ ok: true }); },
  unassignedPatients: () => wait(unassignedPatients),
  assign: (id, { patient_id }) => {
    const p = unassignedPatients.find((x) => x.id === Number(patient_id));
    Object.assign(find(id), { patient_code: p?.patient_code ?? null, sending_without_patient: false, status: 'active' });
    return wait({ ok: true });
  },
  users: () => wait(users),
  userAction: (id, action) => {
    const u = users.find((x) => x.id === Number(id));
    u.status = { approve: 'active', reject: 'rejected', disable: 'disabled', enable: 'active' }[action];
    return wait({ ok: true }, 250);
  },
  requestAccess: () => wait({ ok: true }, 500),
  createUser: (body) => { users.push({ id: Date.now(), username: body.username, email: body.email, role: body.role, status: 'active', created_at: new Date().toISOString() }); return wait({ ok: true }); },
};
