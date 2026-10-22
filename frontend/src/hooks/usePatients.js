import { RefreshGate } from '../utils/refreshGate';
import { useCallback, useEffect, useRef, useState } from 'react';
import { patientsApi } from '../api/patients';
import { POLL_INTERVAL_MS } from '../utils/constants';

// Fetches the active patients and refreshes on an interval. If a refresh
// fails, the last good data stays on screen and `error` is set.
export function usePatients(intervalMs = POLL_INTERVAL_MS) {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const gate = useRef(new RefreshGate());
  const refetch = useCallback(async () => {
    const token = gate.current.start();
    if (!token) return;
    try {
      const { data } = await patientsApi.getAll({ status: 'active' });
      if (!gate.current.isCurrent(token)) return;
      setPatients(data);
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      if (gate.current.isCurrent(token)) setError(e);
    } finally {
      if (gate.current.isCurrent(token)) setLoading(false);
      gate.current.finish(token);
    }
  }, []);

  useEffect(() => {
    refetch();
    const id = setInterval(refetch, intervalMs);
    return () => { clearInterval(id); gate.current.invalidate(); };
  }, [refetch, intervalMs]);

  return { patients, loading, error, lastUpdated, refetch };
}
