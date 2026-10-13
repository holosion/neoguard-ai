import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { adminApi } from '../../api/admin';
import { usePatients } from '../../hooks/usePatients';
import { useFetch } from '../../hooks/useFetch';
import { useAlertStore } from '../../store/alertStore';
import RiskBadge from '../../components/ui/Badge';
import Skeleton from '../../components/ui/Skeleton';
import EmptyState from '../../components/ui/EmptyState';
import AcknowledgeButton from '../../components/alerts/AcknowledgeButton';
import { POLL_INTERVAL_MS, RISK_CATEGORIES, STALE_AFTER_MINUTES } from '../../utils/constants';
import { minutesSince, timeAgo, clock } from '../../utils/formatters';
import { DASH_COLORS, DashboardFrame, DashboardHeading, DashboardPanel, MetricCard } from '../../components/dashboard/DashboardUI';

const TRIAGE_CARDS = [
  { key: 'critical', label: 'Critical patients', tone: 'critical', match: (p) => p.risk_category === 'critical' },
  { key: 'high', label: 'High risk', tone: 'high', match: (p) => p.risk_category === 'high' },
  { key: 'watch', label: 'Watch', tone: 'warning', match: (p) => p.risk_category === 'medium' },
  { key: 'stable', label: 'Stable', tone: 'stable', match: (p) => p.risk_category === 'low' },
  { key: 'no_data', label: 'Stale / no data', tone: 'neutral', match: (p) => p.risk_category === 'no_data' || p.data_status === 'stale' || p.data_status === 'empty' },
];
const RISK_COLORS = { critical: DASH_COLORS.critical, high: DASH_COLORS.high, medium: DASH_COLORS.medium, low: DASH_COLORS.low, no_data: DASH_COLORS.neutral };
const SEVERITIES = ['critical', 'high', 'medium', 'low'];
const tooltipStyle = { background: '#101a29', border: '1px solid #34465f', borderRadius: 10, color: '#eef4fb' };

function activityByWindow(alerts) {
  const now = Date.now();
  const windowMs = 3 * 60 * 60 * 1000;
  const first = now - 8 * windowMs;
  return Array.from({ length: 8 }, (_, index) => {
    const start = first + index * windowMs;
    const end = index === 7 ? now + 1 : start + windowMs;
    const inWindow = alerts.filter((alert) => {
      const at = new Date(alert.created_at).getTime();
      return at >= start && at < end;
    });
    return {
      time: index === 0 ? '24h ago' : new Date(start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      critical: inWindow.filter((alert) => alert.severity === 'critical').length,
      high: inWindow.filter((alert) => alert.severity === 'high').length,
      medium: inWindow.filter((alert) => alert.severity === 'medium').length,
      low: inWindow.filter((alert) => alert.severity === 'low').length,
    };
  });
}

export default function TriagePage() {
  const { patients, loading, error, lastUpdated, refetch } = usePatients();
  const { data: devices, error: devicesError, refetch: refetchDevices } = useFetch(() => adminApi.getClinicalDevices(), { interval: POLL_INTERVAL_MS });
  const { alerts, error: alertsError, refresh: refreshAlerts, acknowledge } = useAlertStore();
  const [filter, setFilter] = useState(null);

  const recentAlerts = useMemo(() => {
    const since = Date.now() - 24 * 60 * 60 * 1000;
    return alerts.filter((alert) => new Date(alert.created_at).getTime() >= since)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [alerts]);
  const filteredPatients = useMemo(() => {
    const card = TRIAGE_CARDS.find((item) => item.key === filter);
    return [...patients].filter((patient) => !card || card.match(patient)).sort((a, b) =>
      (RISK_CATEGORIES[a.risk_category]?.rank ?? 9) - (RISK_CATEGORIES[b.risk_category]?.rank ?? 9) ||
      new Date(b.last_reading_at ?? 0) - new Date(a.last_reading_at ?? 0));
  }, [patients, filter]);
  const riskMix = useMemo(() => [
    { key: 'critical', name: 'Critical', color: RISK_COLORS.critical },
    { key: 'high', name: 'High', color: RISK_COLORS.high },
    { key: 'medium', name: 'Watch', color: RISK_COLORS.medium },
    { key: 'low', name: 'Stable', color: RISK_COLORS.low },
    { key: 'no_data', name: 'No data', color: RISK_COLORS.no_data },
  ].map((item) => ({ ...item, value: patients.filter((patient) => patient.risk_category === item.key).length })).filter((item) => item.value > 0), [patients]);
  const alertActivity = useMemo(() => activityByWindow(recentAlerts), [recentAlerts]);
  const now = Date.now();
  const offlineDevices = (devices ?? []).filter((device) => device.status === 'active' &&
    (!device.last_seen_at || now - new Date(device.last_seen_at).getTime() > STALE_AFTER_MINUTES * 60 * 1000)).length;
  const totalAlerts = recentAlerts.length;
  const refreshAll = () => { refetch(); refetchDevices(); refreshAlerts(); };

  return (
    <DashboardFrame>
      <DashboardHeading title="Ward overview" subtitle="A live view of patient acuity, device connectivity, and recent alerts." updatedAt={lastUpdated} onRefresh={refreshAll} error={error || devicesError || alertsError} />

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 2xl:grid-cols-6">
        {TRIAGE_CARDS.map((card) => (
          <MetricCard key={card.key} label={card.label} value={patients.filter(card.match).length} note="Active monitoring roster" tone={card.tone} icon={card.key} onClick={() => setFilter(filter === card.key ? null : card.key)} active={filter === card.key} />
        ))}
        <MetricCard label="Offline devices" value={devices ? offlineDevices : '—'} note="Active devices quiet for 10+ minutes" tone={offlineDevices ? 'high' : 'blue'} icon="neutral" />
      </div>

      {(error || devicesError || alertsError) && <div role="alert" className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">Could not refresh all ward data. Showing the last available readings where available.</div>}

      <div className="mb-5 grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.85fr)]">
        <DashboardPanel title="Alert activity · last 24 hours" subtitle="Stored alerts grouped into 3-hour windows. No projected or simulated values." className="min-h-[340px]">
          <div className="dashboard-chart" role="img" aria-label="Stacked area chart of recorded alerts by severity over the last 24 hours">
            <ResponsiveContainer>
              <AreaChart data={alertActivity} margin={{ top: 8, right: 10, left: -15, bottom: 0 }}>
                <defs>
                  {SEVERITIES.map((severity) => <linearGradient key={severity} id={`ward-${severity}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={DASH_COLORS[severity]} stopOpacity={0.5} /><stop offset="95%" stopColor={DASH_COLORS[severity]} stopOpacity={0.04} /></linearGradient>)}
                </defs>
                <CartesianGrid stroke={DASH_COLORS.grid} strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: DASH_COLORS.text, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: DASH_COLORS.text, fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#dbe7f5' }} />
                {SEVERITIES.map((severity) => <Area key={severity} type="monotone" dataKey={severity} stackId="alerts" stroke={DASH_COLORS[severity]} fill={`url(#ward-${severity})`} strokeWidth={2} activeDot={{ r: 4 }} />)}
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-400">{SEVERITIES.map((severity) => <span key={severity} className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full" style={{ backgroundColor: DASH_COLORS[severity] }} />{severity[0].toUpperCase() + severity.slice(1)}</span>)}</div>
        </DashboardPanel>

        <DashboardPanel title="Current patient acuity" subtitle={`${patients.length} patients on the active monitoring roster`} className="min-h-[340px]">
          {loading ? <Skeleton rows={4} /> : patients.length === 0 ? <EmptyState message="No patients are currently being monitored." /> : (
            <div className="relative mx-auto h-[250px] max-w-[320px]" role="img" aria-label="Current patient distribution by alert-derived risk category">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={riskMix} dataKey="value" nameKey="name" innerRadius={68} outerRadius={98} paddingAngle={3} stroke="none" isAnimationActive={false}>
                    {riskMix.map((item) => <Cell key={item.name} fill={item.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => [`${value} patients`, name]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-3xl font-semibold text-white">{patients.length}</span><span className="text-xs text-slate-400">monitored</span></div>
            </div>
          )}
          <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
            {riskMix.map((item) => <div key={item.name} className="flex items-center gap-2 text-slate-300"><i className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} /><span className="mr-auto">{item.name}</span><b>{item.value}</b></div>)}
          </div>
        </DashboardPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,0.8fr)]">
        <DashboardPanel title="Patient triage" subtitle="Highest acuity first · select a patient to open their readings and trends" action={<span className="text-xs text-slate-400">{filter ? `Filtered: ${filter}` : `${patients.length} active`}</span>}>
          {loading ? <Skeleton rows={5} /> : filteredPatients.length === 0 ? <EmptyState message={filter ? 'No monitored patients match this category.' : 'No patients currently under monitoring.'} action={filter ? { label: 'Clear filter', onClick: () => setFilter(null) } : undefined} /> : (
            <div className="overflow-x-auto">
              <table className="dashboard-table w-full min-w-[710px] text-left text-sm">
                <thead><tr>{['Patient', 'Risk', 'HR · bpm', 'SpO₂ · %', 'Temp · °C', 'Device', 'Last reading'].map((heading) => <th scope="col" key={heading} className="px-3 py-3 font-medium">{heading}</th>)}</tr></thead>
                <tbody>{filteredPatients.map((patient) => {
                  const stale = patient.data_status === 'stale' || minutesSince(patient.last_reading_at) > STALE_AFTER_MINUTES;
                  const reading = patient.latest_reading;
                  const tint = patient.risk_category === 'critical' ? 'border-l-2 border-l-red-500 bg-red-500/[0.045]' : patient.risk_category === 'high' ? 'border-l-2 border-l-orange-500 bg-orange-500/[0.035]' : '';
                  return <tr key={patient.id} className={`${tint} ${stale ? 'opacity-70' : ''}`}>
                    <td className="px-3 py-3 font-semibold"><Link to={`/patients/${patient.id}`} className="text-brand hover:underline">{patient.patient_code}</Link></td>
                    <td className="px-3 py-3"><RiskBadge category={patient.risk_category} /></td>
                    <td className="px-3 py-3 font-semibold text-white">{reading?.hr ?? '—'}</td>
                    <td className="px-3 py-3 font-semibold text-white">{reading?.spo2 ?? '—'}</td>
                    <td className="px-3 py-3 font-semibold text-white">{reading?.temp == null ? '—' : reading.temp.toFixed(1)}</td>
                    <td className="px-3 py-3">{patient.device_code}</td>
                    <td className="px-3 py-3 text-xs">{patient.last_reading_at ? timeAgo(patient.last_reading_at) : 'No reading'}</td>
                  </tr>;
                })}</tbody>
              </table>
            </div>
          )}
        </DashboardPanel>

        <DashboardPanel title="Recent alerts" subtitle={`${totalAlerts} recorded in the last 24 hours`} action={<Link to="/alerts" className="text-xs font-semibold text-brand hover:underline">All alerts</Link>}>
          {recentAlerts.length === 0 ? <EmptyState message="No alerts were recorded in the last 24 hours." /> : (
            <ul className="divide-y divide-slate-100">
              {recentAlerts.slice(0, 6).map((alert) => (
                <li key={alert.id} className="flex items-start gap-3 py-3">
                  <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: DASH_COLORS[alert.severity] ?? DASH_COLORS.neutral }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><Link to={`/patients/${alert.patient_id}`} className="font-semibold text-white hover:text-blue-300">{alert.patient_code}</Link><RiskBadge category={alert.severity} /><time className="ml-auto text-[11px] text-slate-500">{clock(alert.created_at)}</time></div>
                    <p className="mt-1 text-xs leading-5 text-slate-300">{alert.message}</p>
                    {!alert.acknowledged_at && <div className="mt-2"><AcknowledgeButton onAcknowledge={() => acknowledge(alert.id)} /></div>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </DashboardPanel>
      </div>
    </DashboardFrame>
  );
}
