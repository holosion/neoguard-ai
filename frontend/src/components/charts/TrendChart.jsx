import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { VITAL_THRESHOLDS as T } from '../../utils/constants';
import { clock } from '../../utils/formatters';

export const METRICS = {
  hr: { label: 'Heart rate', unit: 'bpm', domain: [80, 180], bands: [{ y1: 80, y2: T.hr.low, c: '#FEF0E0' }, { y1: T.hr.high, y2: 180, c: '#FEF0E0' }] },
  spo2: { label: 'SpO₂', unit: '%', domain: [80, 100], bands: [{ y1: 80, y2: T.spo2.low, c: '#FDECEA' }] },
  temp: { label: 'Temperature', unit: '°C', domain: [35, 38], bands: [{ y1: T.temp.moderate_low, y2: T.temp.low, c: '#FFF6D6' }, { y1: 35, y2: T.temp.moderate_low, c: '#FDECEA' }] },
};

const SEVERITY_COLOR = { critical: '#B3261E', high: '#B54708', medium: '#8A6100', low: '#1E6B3A' };

export default function TrendChart({ readings, metric, alerts = [] }) {
  const m = METRICS[metric];
  const data = readings.map((r) => ({ t: new Date(r.recorded_at).getTime(), hr: r.hr, spo2: r.spo2, temp: r.temp }));
  if (!data.length) return <p className="py-10 text-center text-slate-500">No readings in this time range.</p>;

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
          <CartesianGrid stroke="#E6EAEF" />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(t) => clock(new Date(t).toISOString())} />
          <YAxis domain={m.domain} unit={` ${m.unit}`} width={70} />
          <Tooltip labelFormatter={(t) => clock(new Date(t).toISOString())} formatter={(v) => [`${v} ${m.unit}`, m.label]} />
          <Line type="monotone" dataKey={metric} stroke="#0F6B6B" strokeWidth={3} dot={false} isAnimationActive={false} />
          {markers.map((k) => (
            <ReferenceDot key={k.id} x={k.x} y={k.y} ifOverflow="visible"
              shape={({ cx, cy }) => <polygon points={`${cx},${cy - 12} ${cx - 7},${cy} ${cx + 7},${cy}`} fill={k.color} />} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
