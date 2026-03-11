import { useQuery } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';

export async function getConfig() {
  const [base, key] = await Promise.all([
    SecureStore.getItemAsync('openclaw_api_base'),
    SecureStore.getItemAsync('openclaw_api_key'),
  ]);
  return {
    base: (base || 'http://localhost:8080').replace(/\/$/, ''),
    key: key || '',
  };
}

export async function fetchPublicData<T>(path: string): Promise<T> {
  const { base, key } = await getConfig();
  const res = await fetch(`${base}${path}`, {
    headers: { 'X-API-Key': key },
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const payload = await res.json();
  return (payload.data || {}) as T;
}

async function fetchSignal(kind: 'btc' | 'kr' | 'us') {
  return fetchPublicData(`/api/v1/signals/${kind}`);
}

export function useSignals(kind: 'btc' | 'kr' | 'us') {
  return useQuery({
    queryKey: ['signals', kind],
    queryFn: () => fetchSignal(kind),
    refetchInterval: 30000,
  });
}
