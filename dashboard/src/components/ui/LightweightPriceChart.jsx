import { AreaSeries, CandlestickSeries, HistogramSeries, LineSeries, createChart } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

function toUnixTime(value, index, fallbackStep = 300) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Date.parse(value || "");
  if (Number.isFinite(parsed)) {
    return Math.floor(parsed / 1000);
  }
  return Math.floor(Date.now() / 1000) - (50 - index) * fallbackStep;
}

function normalize(data) {
  return (Array.isArray(data) ? data : []).map((row, index) => ({
    time: toUnixTime(row?.time || row?.timestamp || row?.date || row?.label, index),
    open: Number(row?.open ?? row?.value ?? row?.close ?? 0),
    high: Number(row?.high ?? row?.value ?? row?.close ?? 0),
    low: Number(row?.low ?? row?.value ?? row?.close ?? 0),
    close: Number(row?.close ?? row?.value ?? 0),
    volume: Number(row?.volume ?? 0),
    value: Number(row?.value ?? row?.close ?? 0),
  }));
}

function readColor(name, fallback) {
  if (typeof window === "undefined") {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export default function LightweightPriceChart({
  data = [],
  title = "Price",
  height = 420,
  showVolume = true,
  priceLine = true,
}) {
  const hostRef = useRef(null);
  const [chartError, setChartError] = useState(null);

  useEffect(() => {
    if (!hostRef.current || !Array.isArray(data) || data.length === 0) {
      return undefined;
    }

    const normalized = normalize(data);
    const hasOhlc = normalized.some((row) => row.open || row.high || row.low);
    const colors = {
      grid: readColor("--chart-grid", "rgba(255,255,255,0.03)"),
      crosshair: readColor("--chart-crosshair", "rgba(255,255,255,0.2)"),
      up: readColor("--chart-candle-up", "#00d4aa"),
      down: readColor("--chart-candle-down", "#ff4757"),
      area: readColor("--accent-us", "#3b82f6"),
    };
    let chart;

    try {
      setChartError(null);
      chart = createChart(hostRef.current, {
        autoSize: true,
        height,
        layout: {
          background: { color: "transparent" },
          textColor: "rgba(232, 232, 237, 0.72)",
          fontFamily: "Inter, sans-serif",
        },
        grid: {
          vertLines: { color: colors.grid },
          horzLines: { color: colors.grid },
        },
        rightPriceScale: {
          borderColor: "rgba(255,255,255,0.08)",
          scaleMargins: { top: 0.08, bottom: showVolume ? 0.22 : 0.08 },
        },
        timeScale: {
          borderColor: "rgba(255,255,255,0.08)",
          timeVisible: true,
          secondsVisible: false,
        },
        crosshair: {
          vertLine: { color: colors.crosshair, width: 1, style: 0 },
          horzLine: { color: colors.crosshair, width: 1, style: 0 },
        },
      });

      if (hasOhlc) {
        const candleSeries = chart.addSeries(CandlestickSeries, {
          upColor: colors.up,
          downColor: colors.down,
          wickUpColor: colors.up,
          wickDownColor: colors.down,
          borderUpColor: colors.up,
          borderDownColor: colors.down,
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

        if (priceLine && normalized.length > 0) {
          candleSeries.createPriceLine({
            price: normalized.at(-1)?.close || 0,
            color: "rgba(247,147,26,0.8)",
            lineWidth: 1,
            axisLabelVisible: true,
            lineStyle: 2,
          });
        }

        if (showVolume) {
          const volumeSeries = chart.addSeries(HistogramSeries, {
            priceFormat: { type: "volume" },
            priceScaleId: "",
          });
          volumeSeries.priceScale().applyOptions({
            scaleMargins: { top: 0.82, bottom: 0 },
          });
          volumeSeries.setData(
            normalized.map((row) => ({
              time: row.time,
              value: row.volume,
              color:
                row.close >= row.open
                  ? "rgba(0,212,170,0.26)"
                  : "rgba(255,71,87,0.26)",
            })),
          );
        }
      } else {
        const areaSeries = chart.addSeries(AreaSeries, {
          lineColor: colors.area,
          topColor: "rgba(59,130,246,0.24)",
          bottomColor: "rgba(59,130,246,0.02)",
          lineWidth: 2,
        });
        areaSeries.setData(normalized.map((row) => ({ time: row.time, value: row.value })));

        const baselineSeries = chart.addSeries(LineSeries, {
          color: "rgba(255,255,255,0.18)",
          lineWidth: 1,
          lineStyle: 2,
        });
        baselineSeries.setData(
          normalized.map((row) => ({
            time: row.time,
            value: normalized[0]?.value || 0,
          })),
        );
      }

      chart.timeScale().fitContent();
    } catch (error) {
      setChartError(error instanceof Error ? error.message : "Chart render failed");
    }

    return () => {
      chart?.remove();
    };
  }, [data, height, priceLine, showVolume]);

  return (
    <div className="h-full min-h-[320px] overflow-hidden rounded-[var(--panel-radius-sm)] border border-white/5 bg-[rgba(7,9,14,0.86)]">
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
          {title}
        </span>
      </div>
      {chartError ? (
        <div className="flex h-[calc(100%-44px)] min-h-[220px] items-center justify-center px-6 text-sm text-[color:var(--text-secondary)]">
          {`Chart unavailable: ${chartError}`}
        </div>
      ) : (
        <div ref={hostRef} className="h-[calc(100%-44px)] min-h-[260px] w-full" />
      )}
    </div>
  );
}
