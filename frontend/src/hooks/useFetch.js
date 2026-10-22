import { RefreshGate } from '../utils/refreshGate';
import { useCallback, useEffect, useRef, useState } from 'react';

// Runs an API call, keeps the last good data if a refresh fails, and can refresh on an interval.
export function useFetch(fn, { deps = [], interval = 0 } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const gate = useRef(new RefreshGate());
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const refetch = useCallback(async () => {
    const token = gate.current.start();
    if (!token) return;
    try {
      const res = await fnRef.current();
      if (!gate.current.isCurrent(token)) return;
      setData(res.data);
      setError(null);
    } catch (e) {
      if (gate.current.isCurrent(token)) setError(e);
    } finally {
      if (gate.current.isCurrent(token)) setLoading(false);
      gate.current.finish(token);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    refetch();
    const t = interval ? setInterval(refetch, interval) : null;
    return () => { clearInterval(t); gate.current.invalidate(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refetch, interval, ...deps]);

  return { data, loading, error, refetch };
}
