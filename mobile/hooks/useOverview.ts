import { useQuery } from '@tanstack/react-query';

import { fetchPublicData } from './useSignals';

type RegimePayload = {
  current_regime?: string;
  confidence?: number;
  history_7d?: Array<{ date: string; regime: string; confidence: number }>;
};

type AllocationPayload = {
  btc_pct?: number;
  kr_pct?: number;
  us_pct?: number;
  cash_pct?: number;
  rebalance_due?: boolean;
  updated_at?: string;
};

export function useRegimeOverview() {
  return useQuery({
    queryKey: ['overview', 'regime'],
    queryFn: () => fetchPublicData<RegimePayload>('/api/v1/signals/regime'),
    refetchInterval: 60000,
  });
}

export function useAllocationOverview() {
  return useQuery({
    queryKey: ['overview', 'allocation'],
    queryFn: () => fetchPublicData<AllocationPayload>('/api/v1/portfolio/allocation'),
    refetchInterval: 60000,
  });
}
