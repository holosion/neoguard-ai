import { vitalStatus, trendArrow } from '../../utils/vitals';
import { latestMetricReading } from '../../utils/readingDisplay';

const META = { hr: ['Heart rate', 'bpm'], spo2: ['SpO₂', '%'], temp: ['Temperature', '°C'] };

export default function VitalsCard({ metric, readings, stale, thresholds, bench = false }) {
  const [defaultLabel, unit] = META[metric];
  const label = bench && metric === 'temp' ? 'Surface temperature' : defaultLabel;
  const reading = bench ? latestMetricReading(readings, metric) : readings[readings.length - 1];
  const value = reading?.[metric] ?? null;
  const estimate = value != null && reading.quality !== 'ok';
  const trendReadings = bench ? readings.filter((item) => item[metric] != null) : readings;
  const status = estimate && metric !== 'temp' ? { ok: true, text: 'Live estimate — hold still' } : vitalStatus(metric, value, thresholds);
  const bad = !status.ok && !stale;
  return (
    <div className={`rounded-xl border p-4 ${bad ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'} ${stale ? 'text-slate-500' : ''}`}>
      <div className="text-sm text-slate-600">{label}</div>
      <div className={`mt-1 text-3xl font-bold ${bad ? 'text-red-800' : ''}`}>
        {value ?? '—'} <span className="text-sm font-normal">{value != null && unit}</span>
      </div>
      <div className={`text-sm font-semibold ${bad ? 'text-red-800' : ''}`}>
        {value != null ? `${trendArrow(trendReadings, metric)}. ${status.text}` : 'No reading'}
      </div>
      {estimate && <p className="mt-2 text-xs text-amber-800">Estimate · signal check not yet passed</p>}
    </div>
  );
}
