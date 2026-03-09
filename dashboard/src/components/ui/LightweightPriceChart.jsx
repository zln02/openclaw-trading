import PropTypes from "prop-types";
import { createChart } from "lightweight-charts";
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
          vertLine: { color: "rgba(139,92,246,0.35)" },
          horzLine: { color: "rgba(59,130,246,0.35)" },
        },
      });

      const series = chart.addAreaSeries({
        topColor: "rgba(59,130,246,0.24)",
        bottomColor: "rgba(59,130,246,0.02)",
        lineColor: "#3b82f6",
        lineWidth: 2,
      });

      const baseTime = Math.floor(Date.now() / 1000) - data.length * 300;
      series.setData(
        data.map((row, index) => ({
          time: baseTime + index * 300,
          value: Number(row.value || 0),
        })),
      );

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
    <div className="glass-card card-pad">
      <div className="panel-title">
        <h2>{title}</h2>
      </div>
      {chartError ? (
        <div className="error-state">{`Chart unavailable: ${chartError}`}</div>
      ) : (
        <div ref={hostRef} style={{ height: 360 }} />
      )}
    </div>
  );
}

LightweightPriceChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  title: PropTypes.string,
};
