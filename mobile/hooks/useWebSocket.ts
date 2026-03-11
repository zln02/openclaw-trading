import { useEffect, useRef, useState } from 'react';
import * as SecureStore from 'expo-secure-store';

export function useWebSocket() {
  const [events, setEvents] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const base = (await SecureStore.getItemAsync('openclaw_api_base')) || 'http://localhost:8080';
      const key = (await SecureStore.getItemAsync('openclaw_api_key')) || '';
      const wsBase = base.replace(/^http/, 'ws').replace(/\/$/, '');
      const ws = new WebSocket(`${wsBase}/api/v1/ws/signals?api_key=${encodeURIComponent(key)}`);
      wsRef.current = ws;
      ws.onmessage = (event) => {
        if (!alive) return;
        try {
          const parsed = JSON.parse(event.data);
          setEvents((prev) => [parsed, ...prev].slice(0, 20));
        } catch {}
      };
    })();
    return () => {
      alive = false;
      wsRef.current?.close();
    };
  }, []);

  return { events };
}
