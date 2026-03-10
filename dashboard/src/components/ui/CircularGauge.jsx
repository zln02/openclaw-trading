import PropTypes from "prop-types";

export default function CircularGauge({ value = 0, label, subtitle, size = 220 }) {
  const clamped = Math.min(Math.max(Number(value) || 0, 0), 100);
  const radius = size / 2 - 18;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;
  const stroke = clamped >= 70 ? "#22c55e" : clamped >= 45 ? "#8b5cf6" : "#ef4444";
  const gradId = `gauge-${String(label || "").replace(/[^a-zA-Z0-9]/g, "")}`;

  return (
    <div style={{ position: "relative", width: size, height: size, margin: "0 auto" }}>
      {/* SVG는 -90도 회전 (12시 방향 시작) */}
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)", display: "block" }}>
        <defs>
          <linearGradient id={gradId} x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="14"
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={clamped >= 70 ? stroke : `url(#${gradId})`}
          strokeWidth="14"
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      {/* 텍스트: SVG 회전과 무관하게 절대 중앙 배치 */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
        }}
      >
        <div
          className="subtle"
          style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: 11, marginBottom: 2 }}
        >
          {label}
        </div>
        <div
          className="mono"
          style={{ color: stroke, fontSize: Math.round(size * 0.19), fontWeight: 800, lineHeight: 1 }}
        >
          {clamped}
        </div>
        {subtitle ? (
          <div className="subtle" style={{ fontSize: 11, marginTop: 4 }}>
            {subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
}

CircularGauge.propTypes = {
  value: PropTypes.number,
  label: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  size: PropTypes.number,
};
