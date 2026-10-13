import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { clock } from '../../utils/formatters';

export const metricsFor = (t) => ({
  hr: { label: 'Heart rate', unit: 'bpm', domain: [80, 180], bands: [{ y1: 80, y2: t.hr_low, c: '#FEF0E0' }, { y1: t.hr_high, y2: 180, c: '#FEF0E0' }] },
  spo2: { label: 'SpO₂', unit: '%', domain: [80, 100], bands: [{ y1: 80, y2: t.spo2_low, c: '#FDECEA' }] },
  temp: { label: 'Temperature', unit: '°C', domain: [35, 38], bands: [{ y1: t.temp_moderate_low, y2: t.temp_low, c: '#FFF6D6' }, { y1: 35, y2: t.temp_moderate_low, c: '#FDECEA' }] },
});

const SEVERITY_COLOR = { critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e' };

export default function TrendChart({ readings, metric, alerts = [], thresholds }) {
  const m = metricsFor(thresholds)[metric];
  const data = readings.filter((r) => r.quality === 'ok' && r[metric] != null).map((r) => ({ t: new Date(r.recorded_at).getTime(), hr: r.hr, spo2: r.spo2, temp: r.temp }));
  if (data.length < 3) return <p className="py-10 text-center text-slate-500">Not enough valid readings to show a trend ({data.length} of 3 required).</p>;

  // Place each alert on the nearest reading for this metric (AI trend alerts show on every chart).
  const markers = alerts
    .filter((a) => a.parameter === metric || a.parameter === 'ai')
    .map((a) => {
      const ts = new Date(a.created_at).getTime();
      if (ts < data[0].t || ts > data[data.length - 1].t) return null;
      const near = data.reduce((best, d) => (Math.abs(d.t - ts) < Math.abs(best.t - ts) ? d : best));
      return { id: a.id, x: near.t, y: near[metric], color: SEVERITY_COLOR[a.severity] ?? '#B3261E' };
    })
    .filter(Boolean);

  return (
    <div style={{ width: '100%', height: 260 }} role="img" aria-label={`${m.label} over the selected time range, with shaded out-of-range bands and alert markers`}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
          {m.bands.map((b, i) => <ReferenceArea key={i} y1={b.y1} y2={b.y2} fill={b.c} ifOverflow="hidden" />)}
          <CartesianGrid stroke="#263449" strokeDasharray="3 5" />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(t) => clock(new Date(t).toISOString())} tick={{ fill: '#a8b6c9', fontSize: 11 }} axisLine={{ stroke: '#34465f' }} tickLine={false} />
          <YAxis domain={m.domain} unit={` ${m.unit}`} width={70} tick={{ fill: '#a8b6c9', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: '#101a29', border: '1px solid #34465f', borderRadius: 10, color: '#eef4fb' }} labelFormatter={(t) => clock(new Date(t).toISOString())} formatter={(v) => [`${v} ${m.unit}`, m.label]} />
          <Line type="monotone" dataKey={metric} stroke="#60a5fa" strokeWidth={3} dot={false} isAnimationActive={false} />
          {markers.map((k) => (
            <ReferenceDot key={k.id} x={k.x} y={k.y} ifOverflow="visible"
              shape={({ cx, cy }) => <polygon points={`${cx},${cy - 12} ${cx - 7},${cy} ${cx + 7},${cy}`} fill={k.color} />} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
