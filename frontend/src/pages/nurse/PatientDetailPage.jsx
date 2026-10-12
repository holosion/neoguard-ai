import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { usePatientDetail } from '../../hooks/usePatientDetail';
import { useAlertStore } from '../../store/alertStore';
import RiskBadge from '../../components/ui/Badge';
import Skeleton from '../../components/ui/Skeleton';
import VitalsCard from '../../components/vitals/VitalsCard';
import StaleIndicator from '../../components/vitals/StaleIndicator';
import TrendChart, { METRICS } from '../../components/charts/TrendChart';
import RiskScorePanel from '../../components/risk/RiskScorePanel';
import AlertTimeline from '../../components/alerts/AlertTimeline';
import { downloadCsv } from '../../utils/csv';
import { recoveredSync } from '../../utils/sync';
import { STALE_AFTER_MINUTES, VITAL_THRESHOLDS as T } from '../../utils/constants';
import { clock, minutesSince, timeAgo } from '../../utils/formatters';

export default function PatientDetailPage() {
  const { id } = useParams();
  const { patient, readings, risk, loading, error, refetch } = usePatientDetail(id);
  const alerts = useAlertStore((s) => s.alerts).filter((a) => a.patient_id === Number(id));
  const acknowledge = useAlertStore((s) => s.acknowledge);
  const [metric, setMetric] = useState('temp');

  if (loading) return <Skeleton rows={6} />;
  if (!patient) {
    return (
      <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        Could not load this patient. Check your connection.
        <button onClick={refetch} className="ml-3 rounded-lg border border-red-600 px-3 py-1 font-semibold">Try again</button>
      </div>
    );
  }

  const stale = patient.data_status ? patient.data_status === 'stale' : minutesSince(patient.last_reading_at) > STALE_AFTER_MINUTES;
  const sync = patient.sync ?? recoveredSync(readings);

  return (
    <div className="space-y-4">
      <Link to="/" className="font-semibold text-brand">← Back to triage</Link>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <h1 className="text-2xl font-bold">{patient.patient_code}</h1>
        <RiskBadge category={patient.risk_category} />
        <span className="text-sm text-slate-500">
          {patient.device_code} · {patient.session_started_at ? `Session since ${clock(patient.session_started_at)}` : 'No session'} · Last reading {timeAgo(patient.last_reading_at)}
        </span>
        <button
          onClick={() => downloadCsv(`${patient.patient_code}-readings.csv`, readings)}
          className="ml-auto min-h-[40px] rounded-lg border border-slate-300 px-4"
        >Export CSV</button>
      </div>

      {error && <p role="alert" className="text-sm text-amber-900">Could not refresh. Showing the last data received.</p>}
      {stale && <StaleIndicator lastReadingAt={patient.last_reading_at} />}
      {sync && sync.lost_count !== undefined && !(sync.lost_count > 0) && (
        <div className="rounded-lg border border-green-300 bg-green-50 p-3 text-sm text-green-900">
          <b>History recovered:</b> {sync.recovered_count} readings recorded offline ({clock(sync.period_start)} to {clock(sync.period_end)}) were saved on the device and synced later.{sync.lost_count === 0 ? ' 0 lost.' : ''}
        </div>
      )}
      {sync && sync.lost_count > 0 && (
        <div role="alert" className="rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          <b>Gap in history:</b> {sync.lost_count} readings between {clock(sync.period_start)} and {clock(sync.period_end)} could not be recovered. The device storage was full.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        {['hr', 'spo2', 'temp'].map((m) => <VitalsCard key={m} metric={m} readings={readings} stale={stale} />)}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">Trend, last 30 min</h2>
          {Object.entries(METRICS).map(([k, v]) => (
            <button key={k} onClick={() => setMetric(k)} aria-pressed={metric === k}
              className={`min-h-[36px] rounded-full border px-4 text-sm ${metric === k ? 'border-brand bg-brand text-white' : 'border-slate-300 bg-white'}`}>
              {v.label}
            </button>
          ))}
        </div>
        <TrendChart readings={readings} metric={metric} alerts={alerts} />
        <p className="mt-2 text-xs text-slate-500">
          Shaded bands show out-of-range values. Triangles mark alerts. Limits: heart rate {T.hr.low} to {T.hr.high} bpm, SpO₂ below {T.spo2.low}%, temperature below {T.temp.low} °C (moderate below {T.temp.moderate_low} °C, severe below {T.temp.severe_low} °C).
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RiskScorePanel risk={risk} />
        <AlertTimeline alerts={alerts} onAcknowledge={acknowledge} />
      </div>
    </div>
  );
}
