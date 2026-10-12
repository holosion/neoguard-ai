import { Link } from 'react-router-dom';
import { patientsApi } from '../../api/patients';
import { useFetch } from '../../hooks/useFetch';
import { POLL_INTERVAL_MS } from '../../utils/constants';

// Lists what staff should check: open sessions with no recent readings, and devices reporting without a patient.
export default function AttentionPanel() {
  const { data } = useFetch(() => patientsApi.getAttention(), { interval: POLL_INTERVAL_MS });
  if (!data?.length) return null;
  return (
    <section aria-label="Needs attention" className="mb-4 rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm text-amber-900">
      <div className="mb-1 font-semibold">Needs attention</div>
      <ul className="space-y-1">
        {data.map((a) => (
          <li key={a.key} className="flex flex-wrap items-center gap-2">
            <span className="flex-1">{a.text}</span>
            <Link to={a.to} className="font-semibold underline">Open</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
