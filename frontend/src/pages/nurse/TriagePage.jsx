import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { usePatients } from '../../hooks/usePatients';
import RiskBadge from '../../components/ui/Badge';
import Skeleton from '../../components/ui/Skeleton';
import EmptyState from '../../components/ui/EmptyState';
import AttentionPanel from '../../components/vitals/AttentionPanel';
import { RISK_CATEGORIES, STALE_AFTER_MINUTES } from '../../utils/constants';
import { minutesSince, timeAgo } from '../../utils/formatters';

const TILES = [
  { key: 'critical', label: 'Critical', match: (p) => p.risk_category === 'critical', color: 'border-t-red-600' },
  { key: 'high', label: 'High', match: (p) => p.risk_category === 'high', color: 'border-t-orange-600' },
  { key: 'stable', label: 'Stable', match: (p) => ['low', 'medium'].includes(p.risk_category), color: 'border-t-green-700' },
  { key: 'no_data', label: 'No data', match: (p) => p.risk_category === 'no_data', color: 'border-t-slate-400' },
];

export default function TriagePage() {
  const { patients, loading, error, lastUpdated, refetch } = usePatients();
  const [filter, setFilter] = useState(null);
  const navigate = useNavigate();

  const sorted = useMemo(() => {
    const tile = TILES.find((t) => t.key === filter);
    return patients
      .filter((p) => (tile ? tile.match(p) : true))
      .sort((a, b) =>
        (RISK_CATEGORIES[a.risk_category]?.rank ?? 9) - (RISK_CATEGORIES[b.risk_category]?.rank ?? 9) ||
        new Date(b.last_reading_at) - new Date(a.last_reading_at)
      );
  }, [patients, filter]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-bold">Triage overview</h1>
        {lastUpdated && <span className="text-sm text-slate-500">Updated {lastUpdated.toLocaleTimeString()}</span>}
        <button onClick={refetch} className="min-h-[40px] rounded-lg border border-slate-300 bg-white px-4">Refresh</button>
      </div>

      {error && (
        <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Could not reach the server. Showing the last data received.
          <button onClick={refetch} className="rounded-lg border border-amber-600 px-3 py-1 font-semibold">Try again</button>
        </div>
      )}

      <AttentionPanel />

      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {TILES.map((t) => (
          <button
            key={t.key}
            onClick={() => setFilter(filter === t.key ? null : t.key)}
            aria-pressed={filter === t.key}
            className={`rounded-xl border border-slate-200 border-t-4 bg-white p-4 text-left ${t.color} ${filter === t.key ? 'ring-2 ring-brand' : ''}`}
          >
            <div className="text-sm text-slate-600">{t.label}</div>
            <div className="text-3xl font-bold">{patients.filter(t.match).length}</div>
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">Patients <span className="font-normal text-slate-500">sorted by risk, then most recent reading</span></h2>
        {loading ? (
          <Skeleton rows={5} />
        ) : sorted.length === 0 ? (
          <EmptyState message="No patients currently under monitoring." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>{['Patient', 'Risk', 'HR', 'SpO₂', 'Temp', 'Device', 'Last reading'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {sorted.map((p) => {
                  const stale = p.data_status ? p.data_status === 'stale' : minutesSince(p.last_reading_at) > STALE_AFTER_MINUTES;
                  const r = p.latest_reading;
                  return (
                    <tr key={p.id} onClick={() => navigate(`/patients/${p.id}`)} className={`cursor-pointer border-t border-slate-100 hover:bg-slate-50 ${stale ? 'text-slate-500' : ''}`}>
                      <td className="px-3 py-3 font-semibold"><Link to={`/patients/${p.id}`} className="text-brand">{p.patient_code}</Link></td>
                      <td className="px-3 py-3"><RiskBadge category={p.risk_category} /></td>
                      <td className="px-3 py-3">{r?.hr ?? '—'}</td>
                      <td className="px-3 py-3">{r ? `${r.spo2}%` : '—'}</td>
                      <td className="px-3 py-3">{r ? `${r.temp} °C` : '—'}</td>
                      <td className="px-3 py-3">{p.device_code}</td>
                      <td className="px-3 py-3">{stale ? `Last: ${timeAgo(p.last_reading_at)}. Data may be outdated.` : timeAgo(p.last_reading_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
