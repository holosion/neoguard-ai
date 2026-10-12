import { useCallback, useEffect, useRef, useState } from 'react';
import { patientsApi } from '../api/patients';
import { POLL_INTERVAL_MS } from '../utils/constants';

// Loads one patient, the last `range` of readings and the risk score, and refreshes them on an interval.
export function usePatientDetail(id, range = '30m', intervalMs = POLL_INTERVAL_MS) {
  const [state, setState] = useState({ patient: null, readings: [], risk: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const seq = useRef(0);

  const refetch = useCallback(async () => {
    const n = ++seq.current; // ignore answers for a patient we have already left
    try {
      const [p, r, k] = await Promise.all([
        patientsApi.getById(id),
        patientsApi.getReadings(id, { range }),
        patientsApi.getRiskScore(id).catch(() => ({ data: null })), // the experimental score must never hide the vitals
      ]);
      if (n !== seq.current) return;
      setState({ patient: p.data, readings: r.data, risk: k.data });
      setError(null);
    } catch (e) {
      if (n === seq.current) setError(e);
    } finally {
      if (n === seq.current) setLoading(false);
    }
  }, [id, range]);

  useEffect(() => {
    setLoading(true);
    refetch();
    const t = setInterval(refetch, intervalMs);
    return () => clearInterval(t);
  }, [refetch, intervalMs]);

  return { ...state, loading, error, refetch };
}
