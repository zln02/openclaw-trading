import { useState, useEffect, useCallback } from "react";

/**
 * Poll an async fetcher at a given interval.
 * Returns { data, error, loading, refresh }.
 */
export default function usePolling(fetcher, intervalMs = 30000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const refresh = useCallback(() => {
    setLoading(true);
    fetcher()
      .then((d) => {
        if (d != null) {
          setData(d);
          setLastUpdated(new Date());
          setError(null);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [fetcher]);

  useEffect(() => {
    refresh();
    if (intervalMs <= 0) return;
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh, lastUpdated };
}
