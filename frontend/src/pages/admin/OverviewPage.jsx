import { Link } from 'react-router-dom';
import { adminApi } from '../../api/admin';
import { useFetch } from '../../hooks/useFetch';
import { POLL_INTERVAL_MS } from '../../utils/constants';
import HealthBadge from '../../components/ui/HealthBadge';
import RiskBadge from '../../components/ui/Badge';
import Skeleton from '../../components/ui/Skeleton';
import { clock } from '../../utils/formatters';

function Tile({ label, value, note, color }) {
  return (
    <div className={`rounded-xl border border-slate-200 border-t-4 bg-white p-4 ${color}`}>
      <div className="text-sm text-slate-600">{label}</div>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm text-slate-500">{note}</div>
    </div>
  );
}

export default function OverviewPage() {
  const { data, loading, error, refetch } = useFetch(() => adminApi.overview(), { interval: POLL_INTERVAL_MS });
  if (loading) return <Skeleton rows={6} />;
  if (!data) {
    return (
      <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        Could not load the system overview.
        <button onClick={refetch} className="ml-3 rounded-lg border border-red-600 px-3 py-1 font-semibold">Try again</button>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-bold">System overview</h1>
        {error && <span role="alert" className="text-sm text-amber-900">Could not refresh. Showing the last data received.</span>}
        <button onClick={refetch} className="min-h-[40px] rounded-lg border border-slate-300 bg-white px-4">Refresh</button>
      </div>

      {data.attention.length > 0 && (
        <div className="rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm text-amber-900">
          <div className="mb-1 font-semibold">Needs attention</div>
          <ul className="space-y-1">
            {data.attention.map((a, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2">
                <span className="flex-1">{a.text}</span>
                <Link to={`/admin/devices/${a.id}`} className="font-semibold underline">Open device</Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Devices online" value={`${data.devices_online}/${data.devices_total}`} note={`${data.devices_total - data.devices_online} not reporting`} color="border-t-brand" />
        <Tile label="Active sessions" value={data.active_sessions} note="Patients being monitored" color="border-t-navy" />
        <Tile label="High and critical alerts" value={data.critical_alerts} note={`${data.unacknowledged_critical} not acknowledged`} color="border-t-red-600" />
        <Tile label="Sync lag" value={`${data.sync_lag_min} min`} note={data.sync_lag_min === 0 ? 'All readings synced' : 'Readings waiting to sync'} color="border-t-green-700" />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">Device health</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>{['Device', 'Health', 'Issue', 'Battery', 'WiFi', 'Storage'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {data.device_health.map((d) => (
                <tr key={d.id} className="border-t border-slate-100">
                  <td className="px-3 py-3"><Link to={`/admin/devices/${d.id}`} className="font-semibold text-brand">{d.device_code}</Link></td>
                  <td className="px-3 py-3"><HealthBadge status={d.health} /></td>
                  <td className="px-3 py-3">{d.issue ?? '—'}</td>
                  <td className="px-3 py-3">{d.battery != null ? `${d.battery}%` : '—'}</td>
                  <td className="px-3 py-3">{d.wifi_dbm != null ? `${d.wifi_dbm} dBm` : '—'}</td>
                  <td className="px-3 py-3">{d.storage_pct != null ? `${d.storage_pct}%` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-2 font-semibold">Recent high and critical alerts</h2>
          {data.recent_alerts.length === 0 ? <p className="text-sm text-slate-500">No high or critical alerts.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.recent_alerts.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-2 py-2">
                  <span className="w-12 text-slate-500">{clock(a.created_at)}</span>
                  <b>{a.patient_code}</b>
                  <RiskBadge category={a.severity} />
                  <span className="flex-1">{a.message}</span>
                  <Link to={`/patients/${a.patient_id}`} className="font-semibold text-brand">View</Link>
                </li>
              ))}
            </ul>
          )}
        </div>
        {data.pending_users !== null && <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-2 font-semibold">Staff access requests</h2>
          {data.pending_users > 0 ? (
            <>
              <p className="mb-3 text-sm text-slate-600">{data.pending_users} staff are waiting for approval and cannot sign in yet.</p>
              <Link to="/admin/users" className="inline-block min-h-[40px] rounded-lg bg-brand px-4 py-2 font-semibold text-white">Review requests</Link>
            </>
          ) : <p className="text-sm text-slate-500">No requests waiting.</p>}
        </div>}
      </div>
    </div>
  );
}
