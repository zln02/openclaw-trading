import { useMemo } from "react";

import LightweightPriceChart from "../../../components/ui/LightweightPriceChart";
import LoadingSkeleton from "../../../components/ui/LoadingSkeleton";
import { ErrorState } from "../../../components/ui/PageState";
import { tradesToMarkers } from "../../../utils/chartAdapters";
import { TIMEFRAMES, useProData } from "../ProDataContext";

export default function ChartPanel() {
  const {
    candles,
    trades,
    tf,
    tfIndex,
    setTfIndex,
    showMarkers,
    setShowMarkers,
    showMa20,
    setShowMa20,
    showMa60,
    setShowMa60,
  } = useProData();

  const candleSeries = useMemo(() => {
    const payload = candles?.data;
    const rows = Array.isArray(payload?.candles)
      ? payload.candles
      : Array.isArray(payload)
        ? payload
        : [];
    return rows.map((row) => ({
      time: row?.time || row?.timestamp,
      open: Number(row?.open ?? row?.opening_price ?? row?.trade_price ?? 0),
      high: Number(row?.high ?? row?.high_price ?? row?.trade_price ?? 0),
      low: Number(row?.low ?? row?.low_price ?? row?.trade_price ?? 0),
      close: Number(row?.close ?? row?.trade_price ?? 0),
      volume: Number(row?.volume ?? row?.candle_acc_trade_volume ?? 0),
      value: Number(row?.close ?? row?.trade_price ?? 0),
    }));
  }, [candles?.data]);

  const tradeRows = useMemo(() => {
    const payload = trades?.data;
    return payload?.trades || payload || [];
  }, [trades?.data]);

  const markers = useMemo(
    () => (showMarkers ? tradesToMarkers(tradeRows) : []),
    [tradeRows, showMarkers],
  );

  const overlays = useMemo(() => {
    const arr = [];
    if (showMa20) arr.push({ type: "sma", period: 20 });
    if (showMa60) arr.push({ type: "sma", period: 60 });
    return arr;
  }, [showMa20, showMa60]);

  const isLoading = candles?.loading && candleSeries.length === 0;
  const errorMsg = candles?.error;

  return (
    <div className="flex h-full flex-col bg-[color:var(--bg-primary)]">
      <div className="flex flex-wrap items-center gap-2 border-b border-white/5 px-3 py-2">
        <div className="flex flex-wrap gap-0.5">
          {TIMEFRAMES.map((t, i) => (
            <button
              key={t.label}
              type="button"
              onClick={() => setTfIndex(i)}
              aria-pressed={tfIndex === i}
              className={`min-h-[28px] rounded-full px-2.5 text-[11px] transition-colors ${
                tfIndex === i
                  ? "bg-white/10 font-medium text-white"
                  : "text-[color:var(--text-secondary)] hover:text-white"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex flex-wrap gap-1">
          <ToggleButton on={showMa20} onClick={() => setShowMa20((v) => !v)}>
            MA20
          </ToggleButton>
          <ToggleButton on={showMa60} onClick={() => setShowMa60((v) => !v)}>
            MA60
          </ToggleButton>
          <ToggleButton on={showMarkers} onClick={() => setShowMarkers((v) => !v)}>
            매매 마커
          </ToggleButton>
        </div>
      </div>
      <div className="min-h-0 flex-1 p-2">
        {isLoading ? (
          <LoadingSkeleton height={320} />
        ) : errorMsg ? (
          <ErrorState message={`BTC 차트 로딩 실패: ${errorMsg}`} />
        ) : (
          <LightweightPriceChart
            title={`BTCKRW · ${tf.label}`}
            data={candleSeries}
            overlays={overlays}
            markers={markers}
          />
        )}
      </div>
    </div>
  );
}

function ToggleButton({ on, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-[10px] transition-colors ${
        on
          ? "bg-[color:var(--accent-btc)]/30 text-white"
          : "bg-white/[0.04] text-[color:var(--text-muted)]"
      }`}
    >
      {children}
    </button>
  );
}
