import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { clock } from '../../utils/formatters';

export default function TelemetryChart({ data, label, unit, domain, threshold }) {
  if (data.length < 2) {
    return (
      <p className="py-10 text-center text-sm text-slate-500">
        {data.length === 1 ? `Latest ${label.toLowerCase()}: ${data[0].v} ${unit}. ` : 'No readings yet. '}History is not available because the backend stores only the latest value.
      </p>
    );
  }
  return (
    <div style={{ width: '100%', height: 200 }} role="img" aria-label={`${label} over the last 24 hours`}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#E6EAEF" />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(t) => clock(new Date(t).toISOString())} />
          <YAxis domain={domain} unit={` ${unit}`} width={70} />
          <Tooltip labelFormatter={(t) => clock(new Date(t).toISOString())} formatter={(v) => [`${v} ${unit}`, label]} />
          {threshold != null && <ReferenceLine y={threshold} stroke="#B3261E" strokeDasharray="5 4" />}
          <Line type="monotone" dataKey="v" stroke="#0F6B6B" strokeWidth={3} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
