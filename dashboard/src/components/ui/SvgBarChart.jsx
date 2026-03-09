import PropTypes from "prop-types";

export default function SvgBarChart({ data = [], color = "#8b5cf6", height = 320, xKey = "label", yKey = "value" }) {
  const values = data.map((item) => Number(item?.[yKey] || 0));
  const max = Math.max(...values, 1);
  const barWidth = 100 / Math.max(data.length, 1);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <svg viewBox="0 0 100 100" width="100%" height={height} preserveAspectRatio="none">
        {data.map((item, index) => {
          const value = Number(item?.[yKey] || 0);
          const normalized = (value / max) * 84;
          return (
            <rect
              key={`${item?.[xKey] || index}`}
              x={index * barWidth + 2}
              y={96 - normalized}
              width={Math.max(barWidth - 4, 3)}
              height={normalized}
              rx="2"
              fill={color}
            />
          );
        })}
      </svg>
      <div style={{ display: "grid", gap: 8 }}>
        {data.map((item, index) => (
          <div key={`${item?.[xKey] || index}`} style={{ display: "grid", gridTemplateColumns: "72px 1fr 48px", gap: 12, alignItems: "center" }}>
            <span className="subtle mono">{item?.[xKey]}</span>
            <div style={{ height: 8, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
              <div
                style={{
                  width: `${(Number(item?.[yKey] || 0) / max) * 100}%`,
                  height: "100%",
                  background: color,
                }}
              />
            </div>
            <span className="mono">{Number(item?.[yKey] || 0).toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

SvgBarChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  color: PropTypes.string,
  height: PropTypes.number,
  xKey: PropTypes.string,
  yKey: PropTypes.string,
};
