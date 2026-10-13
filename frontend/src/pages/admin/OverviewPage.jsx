import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { adminApi } from '../../api/admin';
import { useFetch } from '../../hooks/useFetch';
import { POLL_INTERVAL_MS } from '../../utils/constants';
import HealthBadge from '../../components/ui/HealthBadge';
import RiskBadge from '../../components/ui/Badge';
import Skeleton from '../../components/ui/Skeleton';
import EmptyState from '../../components/ui/EmptyState';
import { clock } from '../../utils/formatters';
import { DASH_COLORS, DashboardFrame, DashboardHeading, DashboardPanel, MetricCard } from '../../components/dashboard/DashboardUI';

const tooltipStyle = { background: '#101a29', border: '1px solid #34465f', borderRadius: 10, color: '#eef4fb' };
const HEALTH_COLORS = { ok: DASH_COLORS.stable, warn: DASH_COLORS.medium, fail: DASH_COLORS.critical };

export default function OverviewPage() {
  const { data, loading, error, refetch } = useFetch(() => adminApi.overview(), { interval: POLL_INTERVAL_MS });
  if (loading) return <DashboardFrame><Skeleton rows={6} /></DashboardFrame>;
  if (!data) {
    return <DashboardFrame><div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">Could not load the system overview.<button onClick={refetch} className="dashboard-button ml-3">Try again</button></div></DashboardFrame>;
  }

  const deviceHealth = ['ok', 'warn', 'fail'].map((health) => ({
    name: health === 'ok' ? 'Healthy' : health === 'warn' ? 'Needs review' : 'Failed',
    value: data.device_health.filter((device) => device.health === health).length,
    color: HEALTH_COLORS[health],
  })).filter((item) => item.value > 0);
  const batteryRows = data.device_health.filter((device) => device.battery != null)
    .map((device) => ({ code: device.device_code, battery: Number(device.battery) }))
    .sort((a, b) => a.battery - b.battery);
  const failedComponents = data.device_health.filter((device) => device.health === 'fail').length;

  return (
    <DashboardFrame>
      <DashboardHeading title="System overview" subtitle="Device fleet health, clinic connectivity, and staff access." onRefresh={refetch} error={error} />

      {data.attention.length > 0 && <div className="mb-5 rounded-xl border border-amber-400/30 bg-amber-400/[0.08] p-4 text-sm text-amber-100">
        <div className="mb-2 font-semibold">Needs attention</div>
        <ul className="space-y-2">{data.attention.map((item, index) => <li key={index} className="flex flex-wrap items-center gap-3"><span className="mr-auto">{item.text}</span><Link to={`/admin/devices/${item.id}`} className="font-semibold text-blue-300 hover:underline">Open device</Link></li>)}</ul>
      </div>}

      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-5">
        <MetricCard label="Devices online" value={`${data.devices_online}/${data.devices_total}`} note={`${Math.max(0, data.devices_total - data.devices_online)} not reporting`} tone={data.devices_online === data.devices_total ? 'stable' : 'warning'} icon="neutral" />
        <MetricCard label="Active sessions" value={data.active_sessions} note="Current device assignments" tone="blue" icon="stable" />
        <MetricCard label="High / critical alerts" value={data.critical_alerts} note={`${data.unacknowledged_critical} unacknowledged · 24h`} tone={data.critical_alerts ? 'critical' : 'stable'} icon="critical" />
        <MetricCard label="Sync lag" value={`${data.sync_lag_min} min`} note={data.sync_lag_min === 0 ? 'All active feeds current' : 'Latest active session delay'} tone={data.sync_lag_min > 10 ? 'warning' : 'stable'} icon="neutral" />
        <MetricCard label="Component failures" value={failedComponents} note="Devices with critical component faults" tone={failedComponents ? 'high' : 'stable'} icon="high" />
      </div>

      <div className="mb-5 grid gap-4 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.5fr)]">
        <DashboardPanel title="Fleet health mix" subtitle={`${data.device_health.length} active devices · latest reported component state`}>
          {data.device_health.length === 0 ? <EmptyState message="No devices are registered yet." /> : (
            <>
              <div className="relative mx-auto h-[230px] max-w-[300px]" role="img" aria-label="Device counts grouped by healthy, needs review, and failed status">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={deviceHealth} dataKey="value" nameKey="name" innerRadius={62} outerRadius={90} paddingAngle={3} stroke="none" isAnimationActive={false}>
                      {deviceHealth.map((item) => <Cell key={item.name} fill={item.color} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value} devices`, 'Count']} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-3xl font-semibold text-white">{data.device_health.length}</span><span className="text-xs text-slate-400">devices</span></div>
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs">{deviceHealth.map((item) => <span key={item.name} className="inline-flex items-center gap-2 text-slate-300"><i className="h-2 w-2 rounded-full" style={{ background: item.color }} />{item.name}<b className="text-white">{item.value}</b></span>)}</div>
            </>
          )}
        </DashboardPanel>

        <DashboardPanel title="Latest battery by device" subtitle="Most recent stored telemetry · 20% low-battery threshold">
          {batteryRows.length === 0 ? <EmptyState message="Battery history will appear after devices send telemetry." /> : (
            <div className="dashboard-chart" role="img" aria-label="Latest battery level percentages for registered devices">
              <ResponsiveContainer>
                <BarChart data={batteryRows} layout="vertical" margin={{ top: 5, right: 20, left: 2, bottom: 0 }}>
                  <CartesianGrid stroke={DASH_COLORS.grid} strokeDasharray="3 5" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fill: DASH_COLORS.text, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="code" width={88} tick={{ fill: DASH_COLORS.text, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}%`, 'Battery']} />
                  <ReferenceLine x={20} stroke={DASH_COLORS.critical} strokeDasharray="4 4" />
                  <Bar dataKey="battery" name="Battery" radius={[0, 5, 5, 0]} maxBarSize={18} isAnimationActive={false}>
                    {batteryRows.map((row) => <Cell key={row.code} fill={row.battery <= 20 ? DASH_COLORS.critical : row.battery <= 40 ? DASH_COLORS.high : DASH_COLORS.stable} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </DashboardPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.85fr)]">
        <DashboardPanel title="Device health" subtitle="Current status and latest telemetry" action={<Link to="/admin/devices" className="text-xs font-semibold text-brand hover:underline">Manage devices</Link>}>
          {data.device_health.length === 0 ? <EmptyState message="No devices are registered yet." action={{ label: 'Register a device', onClick: () => { window.location.href = '/admin/devices'; } }} /> : (
            <div className="overflow-x-auto"><table className="dashboard-table w-full min-w-[650px] text-left text-sm">
              <thead><tr>{['Device', 'Health', 'Issue', 'Battery', 'WiFi'].map((heading) => <th scope="col" key={heading} className="px-3 py-3 font-medium">{heading}</th>)}</tr></thead>
              <tbody>{data.device_health.map((device) => <tr key={device.id}>
                <td className="px-3 py-3"><Link to={`/admin/devices/${device.id}`} className="font-semibold text-brand hover:underline">{device.device_code}</Link></td>
                <td className="px-3 py-3"><HealthBadge status={device.health} /></td>
                <td className="max-w-[240px] px-3 py-3 text-xs">{device.issue ?? '—'}</td>
                <td className="px-3 py-3">{device.battery != null ? `${device.battery}%` : '—'}</td>
                <td className="px-3 py-3">{device.wifi_dbm != null ? `${device.wifi_dbm} dBm` : '—'}</td>
              </tr>)}</tbody>
            </table></div>
          )}
        </DashboardPanel>

        <div className="space-y-4">
          <DashboardPanel title="Recent high and critical alerts" subtitle="Alerts from the last 24 hours">
            {data.recent_alerts.length === 0 ? <EmptyState message="No high or critical alerts in the last 24 hours." /> : <ul className="divide-y divide-slate-100">
              {data.recent_alerts.map((alert) => <li key={alert.id} className="flex flex-wrap items-center gap-2 py-3 text-sm">
                <time className="w-16 shrink-0 text-xs text-slate-400">{clock(alert.created_at)}</time><b className="text-white">{alert.patient_code}</b><RiskBadge category={alert.severity} /><span className="min-w-0 flex-1 text-xs text-slate-300">{alert.message}</span>
              </li>)}
            </ul>}
          </DashboardPanel>

          <DashboardPanel title="Staff access" subtitle="Pending account requests">
            {data.pending_users > 0 ? <><p className="mb-3 text-sm text-slate-300">{data.pending_users} requests need an administrator decision.</p><Link to="/admin/users" className="inline-flex min-h-[40px] items-center rounded-lg bg-brand px-4 text-sm font-semibold text-white">Review requests</Link></> : <p className="text-sm text-slate-400">No staff requests are waiting.</p>}
          </DashboardPanel>
        </div>
      </div>
    </DashboardFrame>
  );
}
