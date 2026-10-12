import { timeAgo } from '../../utils/formatters';

export default function StaleIndicator({ lastReadingAt }) {
  return (
    <div role="status" className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
      <b>Data may be outdated.</b> Last reading {timeAgo(lastReadingAt)}. The device keeps its readings and sends them when it reconnects.
    </div>
  );
}
