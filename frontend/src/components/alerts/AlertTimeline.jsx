import RiskBadge from '../ui/Badge';
import AcknowledgeButton from './AcknowledgeButton';
import { clock } from '../../utils/formatters';

export default function AlertTimeline({ alerts, onAcknowledge }) {
  const sorted = [...alerts].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-2 font-semibold">Alerts timeline</h2>
      {sorted.length === 0 ? (
        <p className="text-sm text-slate-500">No alerts for this patient.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {sorted.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <span className="w-12 text-slate-500">{clock(a.created_at)}</span>
              <RiskBadge category={a.severity} />
              <span className="flex-1">{a.message}</span>
              {a.acknowledged_at ? (
                <span className="text-xs text-slate-500">Acknowledged by {a.acknowledged_by}, {clock(a.acknowledged_at)}</span>
              ) : (
                <AcknowledgeButton onAcknowledge={() => onAcknowledge(a.id)} />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
