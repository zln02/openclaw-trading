import PropTypes from "prop-types";
import { AreaSeries, CandlestickSeries, createChart, HistogramSeries } from "lightweight-charts";
import { useState } from "react";
import { useEffect, useRef } from "react";

export default function LightweightPriceChart({ data = [], title = "BTC Price" }) {
  const hostRef = useRef(null);
  const [chartError, setChartError] = useState(null);

  useEffect(() => {
    if (!hostRef.current || !Array.isArray(data) || data.length === 0) {
      return undefined;
    }

    let chart;

    try {
      setChartError(null);
      chart = createChart(hostRef.current, {
        autoSize: true,
        layout: {
          background: { color: "transparent" },
          textColor: "rgba(232,232,239,0.7)",
        },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.05)" },
          horzLines: { color: "rgba(255,255,255,0.05)" },
        },
        rightPriceScale: {
          borderColor: "rgba(255,255,255,0.08)",
        },
        timeScale: {
          borderColor: "rgba(255,255,255,0.08)",
          timeVisible: true,
          secondsVisible: false,
        },
        crosshair: {
          vertLine: { color: "rgba(139,92,246,0.5)" },
          horzLine: { color: "rgba(139,92,246,0.35)" },
        },
      });

      const baseTime = Math.floor(Date.now() / 1000) - data.length * 300;
      const normalized = data.map((row, index) => ({
        time: baseTime + index * 300,
        open: Number(row.open ?? row.value ?? 0),
        high: Number(row.high ?? row.value ?? 0),
        low: Number(row.low ?? row.value ?? 0),
        close: Number(row.close ?? row.value ?? 0),
        value: Number(row.value ?? row.close ?? 0),
        volume: Number(row.volume ?? 0),
      }));

      const hasOhlc = normalized.some((row) => row.open !== row.close || row.high !== row.low);

      if (hasOhlc) {
        const candleSeries = chart.addSeries(CandlestickSeries, {
          upColor: "#22c55e",
          downColor: "#ef4444",
          wickUpColor: "#22c55e",
          wickDownColor: "#ef4444",
          borderVisible: false,
        });
        candleSeries.setData(
          normalized.map((row) => ({
            time: row.time,
            open: row.open,
            high: row.high,
            low: row.low,
            close: row.close,
          })),
        );

        const volumeSeries = chart.addSeries(HistogramSeries, {
          priceFormat: { type: "volume" },
          priceScaleId: "",
          color: "rgba(139,92,246,0.35)",
        });
        volumeSeries.priceScale().applyOptions({
          scaleMargins: { top: 0.82, bottom: 0 },
        });
        volumeSeries.setData(
          normalized.map((row) => ({
            time: row.time,
            value: row.volume,
            color: row.close >= row.open ? "rgba(34,197,94,0.32)" : "rgba(239,68,68,0.32)",
          })),
        );
      } else {
        const series = chart.addSeries(AreaSeries, {
          topColor: "rgba(139,92,246,0.18)",
          bottomColor: "rgba(139,92,246,0.02)",
          lineColor: "#8b5cf6",
          lineWidth: 2.4,
        });
        series.setData(
          normalized.map((row) => ({
            time: row.time,
            value: row.value,
          })),
        );
      }

      chart.timeScale().fitContent();
    } catch (error) {
      setChartError(error instanceof Error ? error.message : "Chart render failed");
    }

    return () => {
      if (chart) {
        chart.remove();
      }
    };
  }, [data]);

  return (
    <div className="glass-card glass-card--accent card-pad chart-shell">
      <div className="panel-title">
        <h2>{title}</h2>
      </div>
      {chartError ? (
        <div className="error-state">{`Chart unavailable: ${chartError}`}</div>
      ) : (
        <div ref={hostRef} className="chart-host" />
      )}
    </div>
  );
}

LightweightPriceChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  title: PropTypes.string,
};
