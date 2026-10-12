import { useState } from 'react';

export default function AcknowledgeButton({ onAcknowledge }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const click = async () => {
    setBusy(true);
    setFailed(false);
    try { await onAcknowledge(); } catch { setFailed(true); } finally { setBusy(false); }
  };
  return (
    <span className="inline-flex flex-col items-start">
      <button onClick={click} disabled={busy} className="min-h-[36px] rounded-lg bg-brand px-3 text-sm font-semibold text-white disabled:opacity-60">
        {busy ? 'Saving…' : 'Acknowledge'}
      </button>
      {failed && <span role="alert" className="mt-1 text-xs text-red-700">Could not save. Try again.</span>}
    </span>
  );
}
