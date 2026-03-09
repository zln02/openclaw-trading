import PropTypes from "prop-types";

function point(cx, cy, radius, angle, value) {
  const scaled = radius * (value / 100);
  const rad = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + scaled * Math.cos(rad),
    y: cy + scaled * Math.sin(rad),
  };
}

export default function SvgRadarChart({ data = [], size = 320 }) {
  const center = size / 2;
  const radius = size / 2 - 40;
  const angleStep = 360 / Math.max(data.length, 1);

  const polygon = data
    .map((item, index) => {
      const p = point(center, center, radius, angleStep * index, Number(item?.value || 0));
      return `${p.x},${p.y}`;
    })
    .join(" ");

  return (
    <div style={{ display: "grid", placeItems: "center", gap: 18 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {[25, 50, 75, 100].map((step) => {
          const ring = data
            .map((_, index) => {
              const p = point(center, center, radius, angleStep * index, step);
              return `${p.x},${p.y}`;
            })
            .join(" ");
          return (
            <polygon
              key={step}
              points={ring}
              fill="none"
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="1"
            />
          );
        })}
        {data.map((item, index) => {
          const edge = point(center, center, radius, angleStep * index, 100);
          return (
            <line
              key={`${item.factor}-${index}`}
              x1={center}
              y1={center}
              x2={edge.x}
              y2={edge.y}
              stroke="rgba(255,255,255,0.08)"
            />
          );
        })}
        <polygon points={polygon} fill="rgba(139,92,246,0.28)" stroke="#8b5cf6" strokeWidth="2" />
        {data.map((item, index) => {
          const p = point(center, center, radius, angleStep * index, Number(item?.value || 0));
          return <circle key={`${item.factor}-dot`} cx={p.x} cy={p.y} r="4" fill="#8b5cf6" />;
        })}
      </svg>
      <div style={{ display: "grid", gap: 8, width: "100%" }}>
        {data.map((item) => (
          <div key={item.factor} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span className="subtle">{item.factor}</span>
            <span className="mono">{Number(item.value || 0).toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

SvgRadarChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  size: PropTypes.number,
};
