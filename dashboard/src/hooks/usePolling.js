import { useEffect, useRef, useState } from "react";

export default function usePolling(fetcher, intervalMs = 30000, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const fetcherRef = useRef(fetcher);
  const hasDataRef = useRef(false);
  const depsKey = JSON.stringify(deps);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  useEffect(() => {
    let active = true;

    async function refresh() {
      if (!active) {
        return;
      }
      setLoading((prev) => (!hasDataRef.current ? true : prev));
      try {
        const next = await fetcherRef.current();
        if (!active) {
          return;
        }
        setData(next);
        hasDataRef.current = true;
        setError(null);
        setUpdatedAt(new Date());
      } catch (caught) {
        if (!active) {
          return;
        }
        setError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    refresh();
    if (intervalMs <= 0) {
      return () => {
        active = false;
      };
    }
    const id = setInterval(refresh, intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [intervalMs, depsKey]);

  return { data, error, loading, updatedAt };
}
