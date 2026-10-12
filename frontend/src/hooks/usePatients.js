import { useCallback, useEffect, useState } from 'react';
import { patientsApi } from '../api/patients';
import { POLL_INTERVAL_MS } from '../utils/constants';

// Fetches the active patients and refreshes on an interval. If a refresh
// fails, the last good data stays on screen and `error` is set.
export function usePatients(intervalMs = POLL_INTERVAL_MS) {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const refetch = useCallback(async () => {
    try {
      const { data } = await patientsApi.getAll({ status: 'active' });
      setPatients(data);
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
    const id = setInterval(refetch, intervalMs);
    return () => clearInterval(id);
  }, [refetch, intervalMs]);

  return { patients, loading, error, lastUpdated, refetch };
}
