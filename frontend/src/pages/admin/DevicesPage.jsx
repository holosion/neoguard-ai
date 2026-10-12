import { useState } from 'react';
import { Link } from 'react-router-dom';
import { adminApi } from '../../api/admin';
import { useFetch } from '../../hooks/useFetch';
import { POLL_INTERVAL_MS } from '../../utils/constants';
import HealthBadge from '../../components/ui/HealthBadge';
import Skeleton from '../../components/ui/Skeleton';
import EmptyState from '../../components/ui/EmptyState';
import { AssignDeviceModal, DecommissionModal, DeviceFormModal } from '../../components/admin/DeviceModals';
import { timeAgo } from '../../utils/formatters';

const STATUS = { active: 'Active', inactive: 'Inactive', maintenance: 'Maintenance', retired: 'Retired' };
const link = 'min-h-[36px] rounded-lg border border-slate-300 px-3 text-sm';

export default function DevicesPage() {
  const { data: devices, loading, error, refetch } = useFetch(() => adminApi.getDevices(), { interval: POLL_INTERVAL_MS });
  const [modal, setModal] = useState(null); // { type: 'form' | 'assign' | 'decommission', device? }
  const done = () => { setModal(null); refetch(); };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-bold">Devices</h1>
        <button onClick={() => setModal({ type: 'form' })} className="min-h-[40px] rounded-lg bg-brand px-4 font-semibold text-white">Register new device</button>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Could not refresh devices. Showing the last data received.
          <button onClick={refetch} className="ml-3 rounded-lg border border-amber-600 px-3 py-1 font-semibold">Try again</button>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        {loading ? <Skeleton rows={5} /> : !devices?.length ? (
          <EmptyState message="No devices registered yet." action={{ label: 'Register new device', onClick: () => setModal({ type: 'form' }) }} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>{['Code', 'Name', 'Status', 'Patient', 'Health', 'Last seen', 'Actions'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {devices.map((d) => (
                  <tr key={d.id} className={`border-t border-slate-100 ${d.status === 'retired' ? 'text-slate-500' : ''}`}>
                    <td className="px-3 py-3 font-semibold">{d.device_code}</td>
                    <td className="px-3 py-3">{d.name}<div className="text-xs text-slate-500">{d.location}</div></td>
                    <td className="px-3 py-3">{STATUS[d.status]}</td>
                    <td className="px-3 py-3">{d.patient_code ?? (d.sending_without_patient ? <b className="text-amber-800">Sending, no patient</b> : '—')}</td>
                    <td className="px-3 py-3"><HealthBadge status={d.health} /></td>
                    <td className="px-3 py-3">{d.last_seen_at ? timeAgo(d.last_seen_at) : 'Never'}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Link to={`/admin/devices/${d.id}`} className={`${link} inline-flex items-center`}>View health</Link>
                        {d.status !== 'retired' && <button onClick={() => setModal({ type: 'form', device: d })} className={link}>Edit</button>}
                        {d.status !== 'retired' && !d.patient_code && <button onClick={() => setModal({ type: 'assign', device: d })} className={link}>Assign to patient</button>}
                        {d.status !== 'retired' && <button onClick={() => setModal({ type: 'decommission', device: d })} className={`${link} border-red-300 text-red-700`}>Decommission</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modal?.type === 'form' && <DeviceFormModal device={modal.device} onClose={() => setModal(null)} onDone={done} />}
      {modal?.type === 'assign' && <AssignDeviceModal device={modal.device} onClose={() => setModal(null)} onDone={done} />}
      {modal?.type === 'decommission' && <DecommissionModal device={modal.device} onClose={() => setModal(null)} onDone={done} />}
    </div>
  );
}
