import { useEffect, useRef, useState } from "react";
import { AreaSeries, CandlestickSeries, createChart, HistogramSeries } from "lightweight-charts";
import PropTypes from "prop-types";

const COLORS = {
  up: '#22c55e',
  down: '#ef4444',
  accent: '#8b5cf6',
  accentBlue: '#3b82f6',
};

export default function LightweightPriceChart({ data = [], title = "BTC Price" }) {
  const hostRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef({ main: null, volume: null });
  const prevModeRef = useRef(null); // "candle" | "area"
  const [chartError, setChartError] = useState(null);

  // 차트 인스턴스 1회 생성
  useEffect(() => {
    if (!hostRef.current) return;
    try {
      setChartError(null);
      const chart = createChart(hostRef.current, {
        autoSize: true,
        layout: { background: { color: "transparent" }, textColor: "rgba(232,232,239,0.7)" },
        grid: { vertLines: { color: "rgba(255,255,255,0.05)" }, horzLines: { color: "rgba(255,255,255,0.05)" } },
        rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
        timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: true, secondsVisible: false },
        crosshair: { vertLine: { color: "rgba(139,92,246,0.5)" }, horzLine: { color: "rgba(139,92,246,0.35)" } },
      });
      chartRef.current = chart;
    } catch (err) {
      setChartError(err instanceof Error ? err.message : "Chart init failed");
    }
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = { main: null, volume: null };
        prevModeRef.current = null;
      }
    };
  }, []); // 1회만

  // data 변경 시 series 업데이트
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !Array.isArray(data) || data.length === 0) return;

    try {
      const baseTime = Math.floor(Date.now() / 1000) - data.length * 300;
      const normalized = data.map((row, i) => ({
        time: baseTime + i * 300,
        open: Number(row.open ?? row.value ?? 0),
        high: Number(row.high ?? row.value ?? 0),
        low: Number(row.low ?? row.value ?? 0),
        close: Number(row.close ?? row.value ?? 0),
        value: Number(row.value ?? row.close ?? 0),
        volume: Number(row.volume ?? 0),
      }));

      const hasOhlc = normalized.some((r) => r.open !== r.close || r.high !== r.low);
      const mode = hasOhlc ? "candle" : "area";

      // 모드 전환 시에만 series 재생성
      if (prevModeRef.current !== mode) {
        if (seriesRef.current.main) chart.removeSeries(seriesRef.current.main);
        if (seriesRef.current.volume) chart.removeSeries(seriesRef.current.volume);

        if (mode === "candle") {
          seriesRef.current.main = chart.addSeries(CandlestickSeries, {
            upColor: COLORS.up, downColor: COLORS.down,
            wickUpColor: COLORS.up, wickDownColor: COLORS.down,
            borderVisible: false,
          });
          seriesRef.current.volume = chart.addSeries(HistogramSeries, {
            priceFormat: { type: "volume" }, priceScaleId: "", color: "rgba(139,92,246,0.35)",
          });
          seriesRef.current.volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        } else {
          seriesRef.current.main = chart.addSeries(AreaSeries, {
            topColor: "rgba(139,92,246,0.18)", bottomColor: "rgba(139,92,246,0.02)",
            lineColor: COLORS.accent, lineWidth: 2.4,
          });
          seriesRef.current.volume = null;
        }
        prevModeRef.current = mode;
      }

      // 데이터만 업데이트
      if (mode === "candle") {
        seriesRef.current.main.setData(normalized.map((r) => ({ time: r.time, open: r.open, high: r.high, low: r.low, close: r.close })));
        if (seriesRef.current.volume) {
          seriesRef.current.volume.setData(normalized.map((r) => ({
            time: r.time, value: r.volume,
            color: r.close >= r.open ? "rgba(34,197,94,0.32)" : "rgba(239,68,68,0.32)",
          })));
        }
      } else {
        seriesRef.current.main.setData(normalized.map((r) => ({ time: r.time, value: r.value })));
      }

      chart.timeScale().fitContent();
    } catch (err) {
      setChartError(err instanceof Error ? err.message : "Chart update failed");
    }
  }, [data]);

  return (
    <>
      {title && (
        <div className="panel-title"><h2>{title}</h2></div>
      )}
      {chartError ? (
        <div className="error-state">{`Chart unavailable: ${chartError}`}</div>
      ) : (!Array.isArray(data) || data.length === 0) ? (
        <div className="empty-state" style={{ minHeight: 200 }}>
          <span className="subtle">차트 데이터 대기 중...</span>
        </div>
      ) : (
        <div ref={hostRef} className="chart-host" />
      )}
    </>
  );
}

LightweightPriceChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  title: PropTypes.string,
};
