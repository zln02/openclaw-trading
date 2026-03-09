import PropTypes from "prop-types";

export default function MiniChart({ data = [], color = "#8b5cf6", type = "line" }) {
  if (!Array.isArray(data) || data.length === 0) {
    return <div className="skeleton" style={{ height: 44, borderRadius: 12 }} />;
  }

  const values = data.map((item) => Number(item?.value ?? 0));
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);

  if (type === "bar") {
    const width = 100 / data.length;
    return (
      <svg viewBox="0 0 100 44" width="100%" height="44" preserveAspectRatio="none">
        {data.map((item, index) => {
          const height = ((Number(item?.value ?? 0) - min) / range) * 36 + 4;
          return (
            <rect
              key={`${index}-${item?.label ?? "bar"}`}
              x={index * width + 1}
              y={44 - height}
              width={Math.max(width - 2, 2)}
              height={height}
              rx="2"
              fill={color}
              opacity="0.9"
            />
          );
        })}
      </svg>
    );
  }

  const points = data
    .map((item, index) => {
      const x = data.length === 1 ? 50 : (index / (data.length - 1)) * 100;
      const y = 40 - ((Number(item?.value ?? 0) - min) / range) * 32;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 44" width="100%" height="44" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`mini-${color.replace("#", "")}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points}
      />
    </svg>
  );
}

MiniChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  color: PropTypes.string,
  type: PropTypes.oneOf(["line", "bar"]),
};
