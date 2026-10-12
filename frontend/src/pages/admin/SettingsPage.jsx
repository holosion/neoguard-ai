import { POLL_INTERVAL_MS, STALE_AFTER_MINUTES, VITAL_THRESHOLDS as T } from '../../utils/constants';

const rows = [
  ['Temperature, mild low', `Below ${T.temp.low} °C`, 'Medium alert'],
  ['Temperature, moderate low', `Below ${T.temp.moderate_low} °C`, 'High alert'],
  ['Temperature, severe low', `Below ${T.temp.severe_low} °C`, 'Critical alert'],
  ['SpO₂', `Below ${T.spo2.low}%`, 'High alert'],
  ['Heart rate, low', `Below ${T.hr.low} bpm`, 'Medium alert'],
  ['Heart rate, high', `Above ${T.hr.high} bpm`, 'Medium alert'],
];

// Read-only. These values are used for the chart bands and status text. The server decides when alerts are raised.
export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Settings</h1>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-1 font-semibold">Alert thresholds</h2>
        <p className="mb-3 text-sm text-slate-500">These limits are set on the server and shown here for reference. They are provisional and need clinical review. To change them, ask whoever manages the server.</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-600"><tr>{['Measurement', 'Limit', 'Result'].map((h) => <th scope="col" key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody>{rows.map((r) => <tr key={r[0]} className="border-t border-slate-100">{r.map((c, i) => <td key={i} className="px-3 py-3">{c}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
        <h2 className="mb-2 font-semibold">Display</h2>
        <p>Data counts as outdated after {STALE_AFTER_MINUTES} minutes without a reading.</p>
        <p>Pages refresh every {POLL_INTERVAL_MS / 1000} seconds.</p>
      </div>
    </div>
  );
}
