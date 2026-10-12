import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { adminApi } from '../../api/admin';
import { useFetch } from '../../hooks/useFetch';
import { POLL_INTERVAL_MS } from '../../utils/constants';
import HealthBadge from '../../components/ui/HealthBadge';
import Skeleton from '../../components/ui/Skeleton';
import TelemetryChart from '../../components/charts/TelemetryChart';
import { AssignDeviceModal, DecommissionModal, DeviceFormModal } from '../../components/admin/DeviceModals';
import { timeAgo } from '../../utils/formatters';

export default function DeviceDetailPage() {
  const { id } = useParams();
  const { data: d, loading, error, refetch } = useFetch(() => adminApi.getDevice(id), { deps: [id], interval: POLL_INTERVAL_MS });
  const [modal, setModal] = useState(null);

  if (loading) return <Skeleton rows={6} />;
  if (!d) {
    return (
      <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        Could not load this device.
        <button onClick={refetch} className="ml-3 rounded-lg border border-red-600 px-3 py-1 font-semibold">Try again</button>
      </div>
    );
  }
  const done = () => { setModal(null); refetch(); };
  const btn = 'min-h-[40px] rounded-lg border border-slate-300 px-4';

  return (
    <div className="space-y-4">
      <Link to="/admin/devices" className="font-semibold text-brand">← Back to devices</Link>

      <div className={`flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 border-l-4 bg-white p-4 ${d.health === 'fail' ? 'border-l-red-600' : d.health === 'warn' ? 'border-l-yellow-500' : 'border-l-green-700'}`}>
        <h1 className="text-2xl font-bold">{d.device_code}</h1>
        <HealthBadge status={d.health} />
        <span className="text-sm text-slate-500">
          {d.name}, {d.location} · Last seen {d.last_seen_at ? timeAgo(d.last_seen_at) : 'never'} · {d.patient_code ? `Patient ${d.patient_code}` : 'No patient assigned'}
        </span>
        <span className="ml-auto flex flex-wrap gap-2">
          <button onClick={() => setModal('form')} className={btn}>Edit</button>
          {!d.patient_code && d.status !== 'retired' && <button onClick={() => setModal('assign')} className={btn}>Assign to patient</button>}
          {d.status !== 'retired' && <button onClick={() => setModal('decommission')} className={`${btn} border-red-300 text-red-700`}>Decommission</button>}
        </span>
      </div>
      {error && <p role="alert" className="text-sm text-amber-900">Could not refresh. Showing the last data received.</p>}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">Component health</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>{['Component', 'Status', 'Detail', 'Interface'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {d.components.map((c) => (
                <tr key={c.name} className={`border-t border-slate-100 ${c.critical && c.status === 'fail' ? 'bg-red-50' : ''}`}>
                  <td className="px-3 py-3 font-semibold">{c.name}{c.critical && c.status === 'fail' && <span className="ml-2 text-xs font-semibold text-red-800">Critical failure</span>}</td>
                  <td className="px-3 py-3"><HealthBadge status={c.status} /></td>
                  <td className="px-3 py-3">{c.detail}</td>
                  <td className="px-3 py-3">{c.interface}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-2 font-semibold">Battery, last 24 h</h2>
          <TelemetryChart data={d.telemetry.battery} label="Battery" unit="%" domain={[0, 100]} threshold={20} />
          <p className="text-xs text-slate-500">The dashed line marks 20%, the low battery limit.</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-2 font-semibold">WiFi signal, last 24 h</h2>
          <TelemetryChart data={d.telemetry.wifi} label="WiFi signal" unit="dBm" domain={[-100, -40]} threshold={-80} />
          <p className="text-xs text-slate-500">The dashed line marks −80 dBm. Below it the device may struggle to sync.</p>
        </div>
      </div>

      {modal === 'form' && <DeviceFormModal device={d} onClose={() => setModal(null)} onDone={done} />}
      {modal === 'assign' && <AssignDeviceModal device={d} onClose={() => setModal(null)} onDone={done} />}
      {modal === 'decommission' && <DecommissionModal device={d} onClose={() => setModal(null)} onDone={done} />}
    </div>
  );
}
