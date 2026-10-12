const STATUS_TEXT = {
  unmonitored: 'This patient has no active monitoring session.',
  insufficient_data: 'Not enough recent readings to estimate a score yet. The model needs about two minutes of continuous readings.',
  stale: 'The latest reading is too old to estimate a score.',
  model_unavailable: 'The risk model is not available. Threshold alerts still work.',
  disabled: 'The risk model is turned off. Threshold alerts still work.',
  threshold_configuration_mismatch: 'The risk model does not match the current alert thresholds, so it is paused. Threshold alerts still work.',
};

export default function RiskScorePanel({ risk }) {
  const notice = risk?.notice ?? 'Experimental score. It does not replace clinical judgement or the alerts.';
  if (!risk || risk.score == null) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">Experimental risk score</h2>
        <p className="text-sm text-slate-500">{STATUS_TEXT[risk?.status] ?? 'No score available.'}</p>
        <p className="mt-3 text-xs text-slate-500">{notice}</p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-2 flex flex-wrap items-center gap-2 font-semibold">
        Experimental risk score {risk.score.toFixed(2)}
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${risk.warning ? 'bg-orange-100 text-orange-800' : 'bg-green-100 text-green-800'}`}>
          {risk.warning ? 'Warning' : 'No warning'}
        </span>
      </h2>
      {risk.factors.length > 0 && (
        <>
          <p className="mb-1 text-sm text-slate-500">What raised this score</p>
          <ul className="space-y-1 text-sm">
            {risk.factors.map((f) => (
              <li key={f.label} className="flex justify-between">
                <span>{f.label}</span>
                <span className="font-semibold">+{f.contribution.toFixed(2)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-slate-500">Contribution in log-odds. A larger number means more influence on the score.</p>
        </>
      )}
      <p className="mt-3 text-xs text-slate-500">{notice}</p>
    </div>
  );
}
