import { createContext, useContext, useMemo, useState } from "react";

import {
  getBtcCandles,
  getBtcComposite,
  getBtcDecisionLog,
  getBtcFilters,
  getBtcTrades,
} from "../../api";
import usePolling from "../../hooks/usePolling";
import { usePortfolio } from "../../context/PortfolioContext";

const ProDataContext = createContext(null);

export const TIMEFRAMES = [
  { label: "5분",   interval: "minute5",  count: 120, pollMs: 30000  },
  { label: "10분",  interval: "minute10", count: 144, pollMs: 60000  },
  { label: "1시간", interval: "minute60", count: 168, pollMs: 60000  },
  { label: "주봉",  interval: "week",     count: 52,  pollMs: 300000 },
  { label: "월봉",  interval: "month",    count: 48,  pollMs: 300000 },
  { label: "연봉",  interval: "day",      count: 365, pollMs: 300000 },
];

export function ProDataProvider({ children }) {
  const [tfIndex, setTfIndex] = useState(0);
  const tf = TIMEFRAMES[tfIndex];
  const [showMarkers, setShowMarkers] = useState(true);
  const [showMa20, setShowMa20] = useState(true);
  const [showMa60, setShowMa60] = useState(true);

  const composite = usePolling(getBtcComposite, 30000);
  const trades = usePolling(getBtcTrades, 60000);
  const candles = usePolling(
    () => getBtcCandles(tf.interval, tf.count),
    tf.pollMs,
    [tf.interval],
  );
  const decisionLog = usePolling(() => getBtcDecisionLog(20), 30000);
  const filters = usePolling(getBtcFilters, 60000);

  const { btcPortfolio: portfolio } = usePortfolio();

  const value = useMemo(
    () => ({
      composite,
      trades,
      candles,
      decisionLog,
      filters,
      portfolio,
      tfIndex,
      setTfIndex,
      tf,
      showMarkers,
      setShowMarkers,
      showMa20,
      setShowMa20,
      showMa60,
      setShowMa60,
    }),
    [
      composite,
      trades,
      candles,
      decisionLog,
      filters,
      portfolio,
      tfIndex,
      tf,
      showMarkers,
      showMa20,
      showMa60,
    ],
  );

  return <ProDataContext.Provider value={value}>{children}</ProDataContext.Provider>;
}

export function useProData() {
  const ctx = useContext(ProDataContext);
  if (!ctx) {
    throw new Error("useProData must be used within ProDataProvider");
  }
  return ctx;
}
