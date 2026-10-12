// Adapter for the real NeoGuard FastAPI backend (/api/v1).
// It turns the backend's response shapes into the shapes the pages use.
import client from './client';

const get = (url, params) => client.get(url, { params }).then((r) => r.data);
const ok = (data) => ({ data });
async function allPages(url, params = {}, pageSize = 100) {
  const rows = [];
  let offset = 0;
  while (true) {
    const response = await client.get(url, { params: { ...params, limit: pageSize, offset } });
    rows.push(...response.data);
    const next = Number(response.headers['x-next-offset']);
    if (!Number.isFinite(next) || next <= offset) break;
    offset = next;
  }
  return rows;
}
const SEV_RANK = { critical: 0, high: 1, medium: 2, low: 3 };
const PARAM = { temperature_c: 'temp', spo2_percent: 'spo2', heart_rate_bpm: 'hr', quality: 'quality' };

const COMP_LABEL = { rtc_ds3231: 'RTC (DS3231)', max30102: 'MAX30102', ds18b20: 'DS18B20', buzzer: 'Buzzer', lcd: 'LCD', microsd: 'Storage (microSD)' };

const mapReading = (r) => ({
  recorded_at: r.measured_at,
  received_at: r.received_at,
  hr: r.heart_rate_bpm,
  spo2: r.spo2_percent,
  temp: r.temperature_c == null ? null : Number(r.temperature_c),
  quality: r.quality,
});

// ---- patients -------------------------------------------------------------
// Triage category comes from the rule-based alerts (the safe path). The experimental AI warning can raise it to "high".
async function patientList() {
  const [items, devices, alerts] = await Promise.all([
    allPages('/patients'), allPages('/devices'), allPages('/alerts', { acknowledged: false }),
  ]);
  const deviceCode = Object.fromEntries(devices.map((d) => [d.id, d.device_code]));
  const worst = {};
  alerts.forEach((a) => {
    if (SEV_RANK[a.severity] < (SEV_RANK[worst[a.session_id]] ?? 9)) worst[a.session_id] = a.severity;
  });
  return items.map((it) => {
    const s = it.active_session;
    let cat = s ? worst[s.id] : null;
    if (s && !cat) cat = ['empty', 'stale'].includes(it.data_status) ? 'no_data' : 'low';
    if (s && it.risk?.warning && (SEV_RANK[cat] ?? 9) > SEV_RANK.high) cat = 'high';
    const r = it.latest_reading;
    return {
      id: it.patient.id,
      clinic_id: it.patient.clinic_id,
      patient_code: it.patient.patient_code,
      monitored: !!s,
      session_id: s?.id ?? null,
      data_status: it.data_status,
      risk_category: cat ?? 'no_data',
      device_code: s ? deviceCode[s.device_id] ?? '—' : '—',
      last_reading_at: r?.measured_at ?? null,
      latest_reading: r ? { hr: r.heart_rate_bpm, spo2: r.spo2_percent, temp: r.temperature_c == null ? null : Number(r.temperature_c) } : null,
    };
  });
}

const FEATURE_VITAL = { temperature_c: 'Temperature', spo2_percent: 'SpO₂', heart_rate_bpm: 'Heart rate' };
const FEATURE_STAT = { last: 'current value', mean: 'average', slope_per_minute: 'trend', std: 'variability' };
function featureLabel(f) {
  const m = f.match(/^(.*)_(last|mean|slope_per_minute|std)$/);
  return m ? `${FEATURE_VITAL[m[1]] ?? m[1]}, ${FEATURE_STAT[m[2]]}` : f;
}

async function alertList(params = {}) {
  const [alerts, sessions, patients] = await Promise.all([
    allPages('/alerts', params.patient_id ? { patient_id: params.patient_id } : {}),
    allPages('/sessions'), allPages('/patients'),
  ]);
  const code = Object.fromEntries(patients.map((p) => [p.patient.id, p.patient.patient_code]));
  const bySession = Object.fromEntries(sessions.map((s) => [s.id, s.patient_id]));
  return alerts.map((a) => {
    const pid = bySession[a.session_id];
    const meta = a.metadata_json ?? {};
    return {
      id: a.id,
      patient_id: pid,
      patient_code: code[pid] ?? `Patient ${pid}`,
      parameter: PARAM[a.parameter] ?? a.parameter,
      severity: a.severity,
      message: a.message + (meta.historical ? ' (recorded offline, synced later)' : ''),
      created_at: meta.measured_at ?? a.created_at,
      acknowledged_at: a.acknowledged_at,
      acknowledged_by: a.acknowledged_by_user_id ? `user ${a.acknowledged_by_user_id}` : null,
    };
  });
}

// ---- devices ----------------------------------------------------------------
function healthOf(h) {
  if (!h?.components?.length) return 'warn';
  const bad = (h?.components ?? []).filter((c) => !['ok', 'not_checked'].includes(c.status));
  if (bad.some((c) => c.is_critical)) return 'fail';
  if (bad.length || h.components.some((c) => c.status === 'not_checked') || h?.connection_status !== 'online') return 'warn';
  return 'ok';
}

// admin=false skips /admin/device-health (admin only), so nurses and clinicians still get the device list.
async function deviceRows(admin = true) {
  const [devices, health, sessions, patients] = await Promise.all([
    allPages('/devices'), admin ? allPages('/admin/device-health') : Promise.resolve([]), allPages('/sessions'), allPages('/patients'),
  ]);
  const hById = Object.fromEntries(health.map((h) => [h.device_id, h]));
  const code = Object.fromEntries(patients.map((p) => [p.patient.id, p.patient.patient_code]));
  const activeByDevice = Object.fromEntries(sessions.filter((s) => s.status === 'active').map((s) => [s.device_id, s]));
  return devices.map((d) => {
    const h = hById[d.id];
    const s = activeByDevice[d.id];
    const bad = (h?.components ?? []).filter((c) => !['ok', 'not_checked'].includes(c.status));
    return {
      id: d.id,
      clinic_id: d.clinic_id,
      device_code: d.device_code,
      name: d.name ?? d.device_code,
      location: d.location ?? '—',
      status: d.status,
      patient_code: s ? code[s.patient_id] ?? `Patient ${s.patient_id}` : null,
      health: admin ? healthOf(h) : null,
      last_seen_at: d.last_seen_online,
      battery: h?.latest_telemetry?.battery_percent ?? null,
      wifi_dbm: h?.latest_telemetry?.wifi_rssi_dbm ?? null,
      issue: bad.length ? bad.map((c) => `${COMP_LABEL[c.component_type] ?? c.component_type}: ${c.status.replace(/_/g, ' ')}`).join('; ') : !h?.components?.length ? 'No components registered' : h.components.some((c) => c.status === 'not_checked') ? 'Component health not checked yet' : h?.connection_status === 'stale' ? 'No recent contact' : null,
      _health: h,
    };
  });
}

const minutesAgo = (iso) => (iso ? Math.round((Date.now() - new Date(iso).getTime()) / 60000) : null);

const stripPrivate = ({ _health, ...d }) => d;

export const backend = {
  // patients, sessions and devices for the Patients, Sessions and Devices pages
  patientsAll: async () => ok(await patientList()),
  createPatient: (body) => client.post('/patients', body),
  sessions: async () => {
    const [sessions, patients, devices] = await Promise.all([allPages('/sessions'), allPages('/patients'), allPages('/devices')]);
    const pc = Object.fromEntries(patients.map((p) => [p.patient.id, p.patient.patient_code]));
    const dc = Object.fromEntries(devices.map((d) => [d.id, d.device_code]));
    return ok(sessions.map((s) => ({ id: s.id, patient_id: s.patient_id, patient_code: pc[s.patient_id] ?? `Patient ${s.patient_id}`, device_id: s.device_id, device_code: dc[s.device_id] ?? `Device ${s.device_id}`, started_at: s.started_at, ended_at: s.ended_at, status: s.status })));
  },
  startSession: ({ patient_id, device_id }) => client.post('/sessions', { patient_id, device_id }),
  stopSession: (id) => client.post(`/sessions/${id}/stop`),
  availableDevices: async () => ok((await deviceRows(false)).filter((d) => d.status === 'active' && !d.patient_code).map(stripPrivate)),
  devicesBasic: async () => ok((await deviceRows(false)).map(stripPrivate)),
  // Things staff should check: sessions with no recent readings, and devices reporting without a patient.
  attention: async () => {
    const [items, rows] = await Promise.all([patientList(), deviceRows(false)]);
    const out = [];
    items.filter((p) => p.monitored && p.data_status === 'stale').forEach((p) => out.push({ key: `s${p.id}`, text: `${p.patient_code} has had no readings for ${minutesAgo(p.last_reading_at) ?? 'many'} min but its session is still open.`, to: `/patients/${p.id}` }));
    items.filter((p) => p.monitored && p.data_status === 'empty').forEach((p) => out.push({ key: `e${p.id}`, text: `${p.patient_code} has an open session but no readings yet.`, to: `/patients/${p.id}` }));
    rows.filter((d) => d.status === 'active' && !d.patient_code && (minutesAgo(d.last_seen_at) ?? 999) <= 10).forEach((d) => out.push({ key: `d${d.id}`, text: `${d.device_code} is reporting but has no patient assigned.`, to: '/patients' }));
    return ok(out);
  },

  // auth
  me: () => client.get('/auth/me'),
  createUser: (body) => client.post('/auth/users', body),
  requestAccess: (body) => client.post('/auth/request-access', body),
  users: async () => ok(await allPages('/auth/users')),
  userAction: (id, action) => client.patch(`/auth/users/${id}`, { action }),
  clinics: async () => ok(await get('/auth/clinics')),
  createClinic: (body) => client.post('/admin/clinics', body),
  thresholds: async () => ok(await get('/thresholds')),
  accessRequests: async () => ok(await allPages('/auth/access-requests')),
  decideAccessRequest: (id, body) => client.patch(`/auth/access-requests/${id}`, body),

  // patients
  patients: async () => ok((await patientList()).filter((p) => p.monitored)),
  unassignedPatients: async () => {
    const items = await allPages('/patients');
    return ok(items.filter((i) => !i.active_session).map((i) => ({ id: i.patient.id, patient_code: i.patient.patient_code, clinic_id: i.patient.clinic_id })));
  },
  patient: async (id) => {
    let p = (await patientList()).find((x) => x.id === Number(id));
    if (!p) {
      const base = await get(`/patients/${id}`);
      p = { id: base.id, patient_code: base.patient_code, monitored: false, risk_category: 'no_data', device_code: '—', last_reading_at: null, latest_reading: null };
    }
    const sessions = await allPages('/sessions');
    const mine = sessions.filter((s) => s.patient_id === Number(id));
    const s = mine.find((x) => x.status === 'active') ?? mine[0];
    return ok({ ...p, session_started_at: s?.started_at ?? null, sync: null });
  },
  readings: async (id) => {
    const from = new Date(Date.now() - 30 * 60000).toISOString();
    const rows = [];
    let offset = 0;
    while (true) {
      const res = await client.get(`/patients/${id}/readings`, { params: { from, limit: 500, offset } });
      rows.push(...res.data.readings);
      const next = Number(res.headers['x-next-offset']);
      if (!Number.isFinite(next) || next <= offset) break;
      offset = next;
    }
    return ok(rows.map(mapReading).sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at)));
  },
  risk: async (id) => {
    const r = await get(`/patients/${id}/risk-score`);
    const contributions = r.explanation?.contributions ?? [];
    return ok({
      status: r.status,
      score: r.score ?? null,
      category: r.risk_category ?? null,
      warning: !!r.warning,
      notice: r.notice,
      factors: contributions.filter((c) => c.log_odds_contribution > 0.05).slice(0, 3).map((c) => ({ label: featureLabel(c.feature), contribution: c.log_odds_contribution })),
    });
  },

  // alerts
  alerts: async (params) => ok(await alertList(params)),
  acknowledge: (id) => client.post(`/alerts/${id}/acknowledge`),

  // devices and sessions (admin)
  devices: async () => ok((await deviceRows()).map(({ _health, ...d }) => d)),
  device: async (id) => {
    const row = (await deviceRows()).find((d) => d.id === Number(id));
    const h = row._health;
    const t = h?.latest_telemetry;
    const from = new Date(Date.now() - 24 * 60 * 60000).toISOString();
    const history = await allPages(`/devices/${id}/telemetry`, { from }, 500);
    const series = (key) => history.filter((item) => item[key] != null).map((item) => ({ t: new Date(item.reported_at).getTime(), v: Number(item[key]) })).sort((a, b) => a.t - b.t);
    const { _health, ...device } = row;
    return ok({
      ...device,
      components: (h?.components ?? []).map((c) => ({
        name: COMP_LABEL[c.component_type] ?? c.component_type,
        status: c.status === 'ok' ? 'ok' : c.status === 'not_checked' ? 'warn' : c.is_critical ? 'fail' : 'warn',
        detail: c.status === 'ok' ? 'Working' : c.status === 'not_checked' ? 'Not checked yet' : [c.status.replace(/_/g, ' '), c.error_code, c.details ? JSON.stringify(c.details) : null].filter(Boolean).join(' · '),
        interface: c.pin_or_address ?? '—',
        critical: c.is_critical,
      })),
      telemetry: { battery: series('battery_percent'), wifi: series('wifi_rssi_dbm') },
    });
  },
  registerDevice: (body) => client.post('/devices', { clinic_id: body.clinic_id, device_code: body.device_code, name: body.name, location: body.location, status: 'inactive', components: [] }).then((r) => ({ data: r.data })),
  updateDevice: (id, body) => client.patch(`/devices/${id}`, body),
  decommission: (id) => client.patch(`/devices/${id}`, { status: 'retired' }),
  // The backend starts a session at the current time. Back-dating is not supported yet.
  assign: async (id, { patient_id }) => {
    const d = await get(`/devices/${id}`);
    if (d.status !== 'active') await client.patch(`/devices/${id}`, { status: 'active' });
    return client.post('/sessions', { patient_id, device_id: Number(id) });
  },
  overview: async () => {
    const [ov, rows, alerts] = await Promise.all([get('/admin/overview'), deviceRows(), alertList()]);
    const urgent = alerts.filter((a) => ['critical', 'high'].includes(a.severity));
    const monitored = rows.filter((d) => d.patient_code);
    return ok({
      devices_online: ov.devices.online_recently,
      devices_total: ov.devices.active,
      active_sessions: ov.active_sessions,
      critical_alerts: urgent.length,
      unacknowledged_critical: urgent.filter((a) => !a.acknowledged_at).length,
      sync_lag_min: Math.ceil((ov.sync_lag_seconds ?? 0) / 60),
      pending_users: (await backend.accessRequests()).data.filter((request) => request.status === 'pending').length,
      attention: monitored.filter((d) => (minutesAgo(d.last_seen_at) ?? 999) > 30).map((d) => ({ id: d.id, text: `${d.device_code} has sent no readings for ${minutesAgo(d.last_seen_at) ?? 'many'} min but the session for ${d.patient_code} is still open.` })),
      device_health: rows.filter((d) => d.status !== 'retired').map(({ _health, ...d }) => d),
      recent_alerts: urgent.slice(0, 5),
    });
  },
};
