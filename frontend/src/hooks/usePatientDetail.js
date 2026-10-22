import { RefreshGate } from '../utils/refreshGate';
import { useCallback, useEffect, useRef, useState } from 'react';
import { patientsApi } from '../api/patients';
import { POLL_INTERVAL_MS } from '../utils/constants';

// Loads one patient, the last `range` of readings and the risk score, and refreshes them on an interval.
export function usePatientDetail(id, range = '30m', intervalMs = POLL_INTERVAL_MS) {
  const [state, setState] = useState({ patient: null, readings: [], risk: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const gate = useRef(new RefreshGate());

  const refetch = useCallback(async () => {
    const token = gate.current.start();
    if (!token) return;
    try {
      const [p, r, k] = await Promise.all([
        patientsApi.getById(id),
        patientsApi.getReadings(id, { range }),
        patientsApi.getRiskScore(id).catch(() => ({ data: null })), // the experimental score must never hide the vitals
      ]);
      if (!gate.current.isCurrent(token)) return;
      setState({ patient: p.data, readings: r.data, risk: k.data });
      setError(null);
    } catch (e) {
      if (gate.current.isCurrent(token)) setError(e);
    } finally {
      if (gate.current.isCurrent(token)) setLoading(false);
      gate.current.finish(token);
    }
  }, [id, range]);

  useEffect(() => {
    setLoading(true);
    refetch();
    const t = setInterval(refetch, intervalMs);
    return () => { clearInterval(t); gate.current.invalidate(); };
  }, [refetch, intervalMs]);

  return { ...state, loading, error, refetch };
}
