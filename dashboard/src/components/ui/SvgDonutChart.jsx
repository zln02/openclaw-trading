import PropTypes from "prop-types";

function polar(cx, cy, radius, angle) {
  const rad = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(rad),
    y: cy + radius * Math.sin(rad),
  };
}

function arcPath(cx, cy, radius, startAngle, endAngle) {
  const start = polar(cx, cy, radius, endAngle);
  const end = polar(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

export default function SvgDonutChart({ data = [], colors = [], size = 280, strokeWidth = 26 }) {
  const total = data.reduce((sum, item) => sum + Number(item?.value || 0), 0);
  const radius = size / 2 - strokeWidth;
  const center = size / 2;
  let currentAngle = 0;

  return (
    <div style={{ display: "grid", placeItems: "center", gap: 14 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
        />
        {data.map((item, index) => {
          const value = Number(item?.value || 0);
          const angle = total > 0 ? (value / total) * 360 : 0;
          const path = arcPath(center, center, radius, currentAngle, currentAngle + angle);
          const node = (
            <path
              key={`${item?.name || index}`}
              d={path}
              fill="none"
              stroke={colors[index % colors.length] || "#8b5cf6"}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
            />
          );
          currentAngle += angle;
          return node;
        })}
      </svg>
      <div style={{ display: "grid", gap: 8, width: "100%" }}>
        {data.slice(0, 5).map((item, index) => {
          const ratio = total > 0 ? (Number(item.value || 0) / total) * 100 : 0;
          return (
            <div
              key={`${item.name}-${index}`}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 999,
                    background: colors[index % colors.length] || "#8b5cf6",
                    flexShrink: 0,
                  }}
                />
                <span className="subtle" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.name}
                </span>
              </div>
              <span className="mono">{ratio.toFixed(1)}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

SvgDonutChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  colors: PropTypes.arrayOf(PropTypes.string),
  size: PropTypes.number,
  strokeWidth: PropTypes.number,
};
