import { useCallback, useEffect, useRef, useState } from 'react';

// Runs an API call, keeps the last good data if a refresh fails, and can refresh on an interval.
export function useFetch(fn, { deps = [], interval = 0 } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const refetch = useCallback(async () => {
    const n = ++seq.current; // only the newest request may update the screen
    try {
      const res = await fnRef.current();
      if (n !== seq.current) return;
      setData(res.data);
      setError(null);
    } catch (e) {
      if (n === seq.current) setError(e);
    } finally {
      if (n === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    refetch();
    if (!interval) return undefined;
    const t = setInterval(refetch, interval);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refetch, interval, ...deps]);

  return { data, loading, error, refetch };
}
