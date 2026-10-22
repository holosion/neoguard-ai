import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { usePatientDetail } from '../../hooks/usePatientDetail';
import { useFetch } from '../../hooks/useFetch';
import { adminApi } from '../../api/admin';
import { useAlertStore } from '../../store/alertStore';
import RiskBadge from '../../components/ui/Badge';
import Skeleton from '../../components/ui/Skeleton';
import VitalsCard from '../../components/vitals/VitalsCard';
import StaleIndicator from '../../components/vitals/StaleIndicator';
import TrendChart, { metricsFor } from '../../components/charts/TrendChart';
import RiskScorePanel from '../../components/risk/RiskScorePanel';
import AlertTimeline from '../../components/alerts/AlertTimeline';
import { downloadCsv } from '../../utils/csv';
import { recoveredSync } from '../../utils/sync';
import { STALE_AFTER_MINUTES } from '../../utils/constants';
import { clock, minutesSince, timeAgo } from '../../utils/formatters';
import { DashboardFrame, DashboardHeading } from '../../components/dashboard/DashboardUI';

export default function PatientDetailPage() {
  const { id } = useParams();
  const { patient, readings, risk, loading, error, refetch } = usePatientDetail(id);
  const { data: thresholdRows } = useFetch(() => adminApi.getThresholds());
  const alerts = useAlertStore((s) => s.alerts).filter((a) => a.patient_id === Number(id));
  const acknowledge = useAlertStore((s) => s.acknowledge);
  const [metric, setMetric] = useState('temp');

  if (loading) return <DashboardFrame><Skeleton rows={6} /></DashboardFrame>;
  if (!patient) {
    return (
      <DashboardFrame><div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        Could not load this patient. Check your connection.
        <button onClick={refetch} className="ml-3 rounded-lg border border-red-600 px-3 py-1 font-semibold">Try again</button>
      </div></DashboardFrame>
    );
  }

  const limits = Object.fromEntries((thresholdRows ?? []).map((row) => [row.parameter, row.value]));
  const thresholdReady = ['hr_low', 'hr_high', 'spo2_low', 'temp_low', 'temp_moderate_low', 'temp_severe_low'].every((key) => limits[key] !== undefined);
  const stale = patient.data_status ? patient.data_status === 'stale' : minutesSince(patient.last_reading_at) > STALE_AFTER_MINUTES;
  const sync = patient.sync ?? recoveredSync(readings);

  return (
    <DashboardFrame>
      <Link to="/" className="font-semibold text-brand">← Back to triage</Link>

      <DashboardHeading title={patient.patient_code} subtitle={`${patient.device_code} · ${patient.session_started_at ? `Session started ${clock(patient.session_started_at)}` : 'No active session'} · Last reading ${timeAgo(patient.last_reading_at)}`} updatedAt={patient.last_reading_at ? new Date(patient.last_reading_at) : null} onRefresh={refetch} error={error} />

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <RiskBadge category={patient.risk_category} />
        <span className="text-sm text-slate-400">Live data refreshes every 5 seconds. The device publishes after a 60-second signal check; unstable readings are withheld.</span>
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
        {thresholdReady ? ['hr', 'spo2', 'temp'].map((m) => <VitalsCard key={m} metric={m} readings={readings} stale={stale} thresholds={{ hr: { low: limits.hr_low, high: limits.hr_high }, spo2: { low: limits.spo2_low }, temp: { low: limits.temp_low, moderate_low: limits.temp_moderate_low, severe_low: limits.temp_severe_low } }} />) : <p className="col-span-3 py-4 text-center text-sm text-slate-500">Loading server threshold configuration…</p>}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">Trend, last 30 min</h2>
          {Object.entries(thresholdReady ? metricsFor(limits) : {}).map(([k, v]) => (
            <button key={k} onClick={() => setMetric(k)} aria-pressed={metric === k}
              className={`min-h-[36px] rounded-full border px-4 text-sm ${metric === k ? 'border-brand bg-brand text-white' : 'border-slate-300 bg-white'}`}>
              {v.label}
            </button>
          ))}
        </div>
        {thresholdReady ? <TrendChart readings={readings} metric={metric} alerts={alerts} thresholds={limits} /> : <p className="py-10 text-center text-slate-500">Loading server threshold configuration…</p>}
        {thresholdReady && <p className="mt-2 text-xs text-slate-500">Shaded bands show server configured out-of-range values. Triangles mark alerts.</p>}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RiskScorePanel risk={risk} />
        <AlertTimeline alerts={alerts} onAcknowledge={acknowledge} />
      </div>
    </DashboardFrame>
  );
}
