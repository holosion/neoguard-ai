import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAlertStore, selectUnacknowledged } from '../../store/alertStore';
import { useAuthStore } from '../../store/authStore';
import RiskBadge from '../../components/ui/Badge';
import Skeleton from '../../components/ui/Skeleton';
import EmptyState from '../../components/ui/EmptyState';
import AcknowledgeButton from '../../components/alerts/AcknowledgeButton';
import { PARAMETER_LABELS } from '../../utils/constants';
import { clock } from '../../utils/formatters';

export default function AlertsPage() {
  const isAdmin = useAuthStore((state) => state.user?.role === 'admin');
  const { alerts, loading, error, refresh, acknowledge } = useAlertStore();
  const unack = useAlertStore(selectUnacknowledged);
  const [filter, setFilter] = useState('all');
  const [param, setParam] = useState('');

  const shown = alerts
    .filter((a) => (filter === 'unack' ? !a.acknowledged_at : filter === 'critical' ? a.severity === 'critical' : true))
    .filter((a) => (param ? a.parameter === param : true))
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const chip = (key, label) => (
    <button key={key} onClick={() => setFilter(key)} aria-pressed={filter === key}
      className={`min-h-[36px] rounded-full border px-4 text-sm ${filter === key ? 'border-brand bg-brand text-white' : 'border-slate-300 bg-white'}`}>{label}</button>
  );

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h1 className="mr-auto text-2xl font-bold">Alerts</h1>
        <button onClick={refresh} className="min-h-[40px] rounded-lg border border-slate-300 bg-white px-4">Refresh</button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {chip('all', 'All')}
        {chip('unack', `Unacknowledged (${unack})`)}
        {chip('critical', 'Critical')}
        <label className="ml-2 text-sm text-slate-600">
          Parameter{' '}
          <select value={param} onChange={(e) => setParam(e.target.value)} className="min-h-[36px] rounded-lg border border-slate-300 bg-white px-2">
            <option value="">All</option>
            {Object.entries(PARAMETER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Could not refresh alerts. Showing the last data received.
          <button onClick={refresh} className="ml-3 rounded-lg border border-amber-600 px-3 py-1 font-semibold">Try again</button>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        {loading ? <Skeleton rows={4} /> : shown.length === 0 ? (
          <EmptyState message={filter === 'unack' ? 'Every alert has been acknowledged.' : 'No alerts match these filters.'} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>{['Time', 'Patient', 'Alert', 'Severity', 'Status', 'Action'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {shown.map((a) => (
                  <tr key={a.id} className={`border-t border-slate-100 ${a.acknowledged_at ? 'text-slate-500' : ''}`}>
                    <td className="px-3 py-3">{clock(a.created_at)}</td>
                    <td className="px-3 py-3">{isAdmin ? <span className="font-semibold">{a.patient_code}</span> : <Link to={`/patients/${a.patient_id}`} className="font-semibold text-brand">{a.patient_code}</Link>}</td>
                    <td className="px-3 py-3">{a.message}</td>
                    <td className="px-3 py-3"><RiskBadge category={a.severity} /></td>
                    <td className="px-3 py-3">{a.acknowledged_at ? `Acknowledged by ${a.acknowledged_by}, ${clock(a.acknowledged_at)}` : 'Not acknowledged'}</td>
                    <td className="px-3 py-3">{!a.acknowledged_at && <AcknowledgeButton onAcknowledge={() => acknowledge(a.id)} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
