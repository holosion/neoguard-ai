import { useFetch } from '../../hooks/useFetch';
import { adminApi } from '../../api/admin';
import Skeleton from '../../components/ui/Skeleton';
import { POLL_INTERVAL_MS, STALE_AFTER_MINUTES } from '../../utils/constants';

export default function SettingsPage() {
  const { data: rows, loading, error, refetch } = useFetch(() => adminApi.getThresholds());
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Settings</h1>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-1 font-semibold">Alert thresholds</h2>
        <p className="mb-3 text-sm text-slate-500">Current server values are shown here. The server evaluates readings against these limits.</p>
        {loading ? <Skeleton rows={4} /> : error ? <p role="alert" className="text-sm text-red-700">Could not load server thresholds. <button onClick={refetch} className="underline">Retry</button></p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[540px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-600"><tr>{['Parameter', 'Value', 'Unit', 'Version', 'Source'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody>{(rows ?? []).map((row) => <tr key={row.parameter} className="border-t border-slate-100"><td className="px-3 py-3">{row.parameter.replaceAll('_', ' ')}</td><td className="px-3 py-3 font-semibold">{row.value}</td><td className="px-3 py-3">{row.unit}</td><td className="px-3 py-3">{row.version}</td><td className="px-3 py-3">{row.source}</td></tr>)}</tbody>
          </table></div>
        )}
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm"><h2 className="mb-2 font-semibold">Display</h2><p>Data counts as outdated after {STALE_AFTER_MINUTES} minutes without a reading.</p><p>Pages refresh every {POLL_INTERVAL_MS / 1000} seconds.</p></div>
    </div>
  );
}
