import { useEffect, useRef, useState, useCallback } from "react";

export default function usePolling(fetcher, intervalMs = 30000, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const fetcherRef = useRef(fetcher);
  const hasDataRef = useRef(false);
  const errorCountRef = useRef(0);
  const timerRef = useRef(null);
  const depsKey = JSON.stringify(deps);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const isStale = updatedAt
    ? Date.now() - updatedAt.getTime() > intervalMs * 3
    : true;

  useEffect(() => {
    let active = true;

    function getBackoffInterval() {
      if (errorCountRef.current === 0) return intervalMs;
      const backoff = Math.min(intervalMs * Math.pow(2, errorCountRef.current), 300000);
      return backoff;
    }

    async function refresh() {
      if (!active) return;
      setLoading((prev) => (!hasDataRef.current ? true : prev));
      try {
        const next = await fetcherRef.current();
        if (!active) return;
        setData(next);
        hasDataRef.current = true;
        setError(null);
        setUpdatedAt(new Date());
        errorCountRef.current = 0;
      } catch (caught) {
        if (!active) return;
        errorCountRef.current += 1;
        setError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        if (active) {
          setLoading(false);
          scheduleNext();
        }
      }
    }

    function scheduleNext() {
      if (!active || intervalMs <= 0) return;
      const delay = getBackoffInterval();
      timerRef.current = setTimeout(refresh, delay);
    }

    function handleVisibility() {
      if (document.hidden) {
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
      } else {
        refresh();
      }
    }

    document.addEventListener("visibilitychange", handleVisibility);
    refresh();

    return () => {
      active = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [intervalMs, depsKey]);

  return { data, error, loading, updatedAt, isStale };
}
