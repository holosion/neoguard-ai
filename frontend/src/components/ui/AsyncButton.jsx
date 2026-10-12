import { useState } from 'react';

// A button that runs an async action, shows progress, and shows an error if it fails.
export default function AsyncButton({ onClick, children, busyLabel = 'Saving…', className = '' }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const click = async () => {
    setBusy(true);
    setFailed(false);
    try { await onClick(); } catch { setFailed(true); } finally { setBusy(false); }
  };
  return (
    <span className="inline-flex flex-col items-start">
      <button onClick={click} disabled={busy} className={`min-h-[36px] rounded-lg px-3 text-sm font-semibold disabled:opacity-60 ${className}`}>
        {busy ? busyLabel : children}
      </button>
      {failed && <span role="alert" className="mt-1 text-xs text-red-700">Could not save. Try again.</span>}
    </span>
  );
}
