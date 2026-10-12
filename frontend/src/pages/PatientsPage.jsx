import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { patientsApi } from '../api/patients';
import { useFetch } from '../hooks/useFetch';
import { useAuthStore } from '../store/authStore';
import RiskBadge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import EmptyState from '../components/ui/EmptyState';
import { EndSessionModal, PatientFormModal, StartSessionModal } from '../components/patients/SessionModals';
import { POLL_INTERVAL_MS, SESSION_MANAGER_ROLES } from '../utils/constants';
import { timeAgo } from '../utils/formatters';

export default function PatientsPage() {
  const role = useAuthStore((s) => s.user?.role);
  const canManage = SESSION_MANAGER_ROLES.includes(role);
  const { data: patients, loading, error, refetch } = useFetch(() => patientsApi.getAllWithStatus(), { interval: POLL_INTERVAL_MS });
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [modal, setModal] = useState(null); // { type: 'register' | 'start' | 'end', patient? }
  const done = () => { setModal(null); refetch(); };

  const shown = useMemo(
    () => (patients ?? [])
      .filter((p) => (filter === 'monitored' ? p.monitored : filter === 'idle' ? !p.monitored : true))
      .filter((p) => p.patient_code.toLowerCase().includes(query.trim().toLowerCase())),
    [patients, filter, query]
  );

  const chip = (key, label) => (
    <button key={key} onClick={() => setFilter(key)} aria-pressed={filter === key}
      className={`min-h-[36px] rounded-full border px-4 text-sm ${filter === key ? 'border-brand bg-brand text-white' : 'border-slate-300 bg-white'}`}>{label}</button>
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-bold">Patients</h1>
        {canManage && <button onClick={() => setModal({ type: 'register' })} className="min-h-[40px] rounded-lg bg-brand px-4 font-semibold text-white">Register patient</button>}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {chip('all', 'All')}{chip('monitored', 'Monitored')}{chip('idle', 'Not monitored')}
        <label className="ml-auto text-sm text-slate-600">
          <span className="sr-only">Search by patient code</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by code" className="min-h-[36px] rounded-lg border border-slate-300 bg-white px-3" />
        </label>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Could not refresh patients. Showing the last data received.
          <button onClick={refetch} className="ml-3 rounded-lg border border-amber-600 px-3 py-1 font-semibold">Try again</button>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        {loading ? <Skeleton rows={5} /> : shown.length === 0 ? (
          <EmptyState message={patients?.length ? 'No patients match these filters.' : 'No patients registered yet.'}
            action={canManage && !patients?.length ? { label: 'Register patient', onClick: () => setModal({ type: 'register' }) } : undefined} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>{['Patient', 'Monitoring', 'Device', 'Risk', 'Last reading', 'Actions'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {shown.map((p) => (
                  <tr key={p.id} className={`border-t border-slate-100 ${p.monitored ? '' : 'text-slate-500'}`}>
                    <td className="px-3 py-3 font-semibold"><Link to={`/patients/${p.id}`} className="text-brand">{p.patient_code}</Link></td>
                    <td className="px-3 py-3">{p.monitored ? 'Monitored' : 'Not monitored'}</td>
                    <td className="px-3 py-3">{p.device_code}</td>
                    <td className="px-3 py-3">{p.monitored ? <RiskBadge category={p.risk_category} /> : '—'}</td>
                    <td className="px-3 py-3">{p.monitored ? timeAgo(p.last_reading_at) : '—'}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Link to={`/patients/${p.id}`} className="inline-flex min-h-[36px] items-center rounded-lg border border-slate-300 px-3">View</Link>
                        {canManage && (p.monitored
                          ? <button onClick={() => setModal({ type: 'end', patient: p })} className="min-h-[36px] rounded-lg border border-red-300 px-3 text-red-700">End session</button>
                          : <button onClick={() => setModal({ type: 'start', patient: p })} className="min-h-[36px] rounded-lg bg-brand px-3 font-semibold text-white">Start session</button>)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modal?.type === 'register' && <PatientFormModal onClose={() => setModal(null)} onDone={done} />}
      {modal?.type === 'start' && <StartSessionModal patient={modal.patient} onClose={() => setModal(null)} onDone={done} />}
      {modal?.type === 'end' && <EndSessionModal sessionId={modal.patient.session_id} patientCode={modal.patient.patient_code} onClose={() => setModal(null)} onDone={done} />}
    </div>
  );
}
