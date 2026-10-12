import { useState } from 'react';
import { Link } from 'react-router-dom';
import { sessionsApi } from '../../api/sessions';
import { useFetch } from '../../hooks/useFetch';
import Skeleton from '../../components/ui/Skeleton';
import EmptyState from '../../components/ui/EmptyState';
import { EndSessionModal } from '../../components/patients/SessionModals';
import { POLL_INTERVAL_MS } from '../../utils/constants';
import { clock } from '../../utils/formatters';

const day = (iso) => new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short' });

export default function SessionsPage() {
  const { data: sessions, loading, error, refetch } = useFetch(() => sessionsApi.list(), { interval: POLL_INTERVAL_MS });
  const [filter, setFilter] = useState('all');
  const [ending, setEnding] = useState(null);
  const shown = (sessions ?? [])
    .filter((s) => (filter === 'active' ? s.status === 'active' : filter === 'ended' ? s.status !== 'active' : true))
    .sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
  const chip = (key, label) => (
    <button key={key} onClick={() => setFilter(key)} aria-pressed={filter === key}
      className={`min-h-[36px] rounded-full border px-4 text-sm ${filter === key ? 'border-brand bg-brand text-white' : 'border-slate-300 bg-white'}`}>{label}</button>
  );
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Sessions</h1>
      <div className="mb-4 flex gap-2">{chip('all', 'All')}{chip('active', 'Active')}{chip('ended', 'Ended')}</div>
      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Could not refresh sessions. Showing the last data received.
          <button onClick={refetch} className="ml-3 rounded-lg border border-amber-600 px-3 py-1 font-semibold">Try again</button>
        </div>
      )}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        {loading ? <Skeleton rows={5} /> : shown.length === 0 ? <EmptyState message="No sessions match this filter." /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600"><tr>{['Patient', 'Device', 'Started', 'Ended', 'Status', 'Action'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {shown.map((s) => (
                  <tr key={s.id} className={`border-t border-slate-100 ${s.status === 'active' ? '' : 'text-slate-500'}`}>
                    <td className="px-3 py-3 font-semibold"><Link to={`/patients/${s.patient_id}`} className="text-brand">{s.patient_code}</Link></td>
                    <td className="px-3 py-3">{s.device_code}</td>
                    <td className="px-3 py-3">{day(s.started_at)}, {clock(s.started_at)}</td>
                    <td className="px-3 py-3">{s.ended_at ? `${day(s.ended_at)}, ${clock(s.ended_at)}` : '—'}</td>
                    <td className="px-3 py-3">{s.status === 'active' ? 'Active' : 'Ended'}</td>
                    <td className="px-3 py-3">{s.status === 'active' && <button onClick={() => setEnding(s)} className="min-h-[36px] rounded-lg border border-red-300 px-3 text-red-700">End session</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {ending && <EndSessionModal sessionId={ending.id} patientCode={ending.patient_code} onClose={() => setEnding(null)} onDone={() => { setEnding(null); refetch(); }} />}
    </div>
  );
}
