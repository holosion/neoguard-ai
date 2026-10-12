const MAP = {
  ok: ['OK', 'bg-green-100 text-green-800'],
  warn: ['Warning', 'bg-yellow-100 text-yellow-800'],
  fail: ['Failed', 'bg-red-100 text-red-800'],
};

export default function HealthBadge({ status }) {
  const [label, cls] = MAP[status] ?? MAP.ok;
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>{label}</span>;
}
