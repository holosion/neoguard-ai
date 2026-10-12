import { devicesApi } from '../../api/sessions';
import { useFetch } from '../../hooks/useFetch';
import Skeleton from '../../components/ui/Skeleton';
import EmptyState from '../../components/ui/EmptyState';
import { POLL_INTERVAL_MS, STALE_AFTER_MINUTES } from '../../utils/constants';
import { minutesSince, timeAgo } from '../../utils/formatters';

const STATUS = { active: 'Active', inactive: 'Inactive', maintenance: 'Maintenance', retired: 'Retired' };

// Read-only list for clinical staff. Device management is on the admin pages.
export default function NurseDevicesPage() {
  const { data: devices, loading, error, refetch } = useFetch(() => devicesApi.list(), { interval: POLL_INTERVAL_MS });
  const rows = (devices ?? []).filter((d) => d.status !== 'retired');
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Devices</h1>
      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Could not refresh devices. Showing the last data received.
          <button onClick={refetch} className="ml-3 rounded-lg border border-amber-600 px-3 py-1 font-semibold">Try again</button>
        </div>
      )}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        {loading ? <Skeleton rows={4} /> : rows.length === 0 ? <EmptyState message="No devices registered yet." /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600"><tr>{['Device', 'Location', 'Status', 'In use by', 'Last contact'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {rows.map((d) => {
                  const silent = d.last_seen_at && minutesSince(d.last_seen_at) > STALE_AFTER_MINUTES;
                  return (
                    <tr key={d.id} className="border-t border-slate-100">
                      <td className="px-3 py-3 font-semibold">{d.device_code}</td>
                      <td className="px-3 py-3">{d.location}</td>
                      <td className="px-3 py-3">{STATUS[d.status] ?? d.status}</td>
                      <td className="px-3 py-3">{d.patient_code ?? 'Free'}</td>
                      <td className={`px-3 py-3 ${silent ? 'text-amber-800' : ''}`}>{d.last_seen_at ? timeAgo(d.last_seen_at) : 'Never'}{silent && d.patient_code ? '. Check this device.' : ''}</td>
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
