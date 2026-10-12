import { vitalStatus, trendArrow } from '../../utils/vitals';

const META = { hr: ['Heart rate', 'bpm'], spo2: ['SpO₂', '%'], temp: ['Temperature', '°C'] };

export default function VitalsCard({ metric, readings, stale }) {
  const [label, unit] = META[metric];
  const value = readings.length ? readings[readings.length - 1][metric] : null;
  const status = vitalStatus(metric, value);
  const bad = !status.ok && !stale;
  return (
    <div className={`rounded-xl border p-4 ${bad ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'} ${stale ? 'text-slate-500' : ''}`}>
      <div className="text-sm text-slate-600">{label}</div>
      <div className={`mt-1 text-3xl font-bold ${bad ? 'text-red-800' : ''}`}>
        {value ?? '—'} <span className="text-sm font-normal">{value != null && unit}</span>
      </div>
      <div className={`text-sm font-semibold ${bad ? 'text-red-800' : ''}`}>
        {value != null ? `${trendArrow(readings, metric)}. ${status.text}` : 'No reading'}
      </div>
    </div>
  );
}
