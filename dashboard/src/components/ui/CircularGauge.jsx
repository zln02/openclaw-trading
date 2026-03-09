import PropTypes from "prop-types";

export default function CircularGauge({ value = 0, label, subtitle, size = 220 }) {
  const clamped = Math.min(Math.max(Number(value) || 0, 0), 100);
  const radius = size / 2 - 18;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;
  const stroke = clamped >= 70 ? "#22c55e" : clamped >= 45 ? "#8b5cf6" : "#ef4444";

  return (
    <div style={{ display: "grid", placeItems: "center", gap: 12 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <defs>
          <linearGradient id={`gauge-${label}`} x1="0%" x2="100%" y1="0%" y2="100%">
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
          stroke={stroke === "#22c55e" ? stroke : `url(#gauge-${label})`}
          strokeWidth="14"
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div style={{ marginTop: `-${size * 0.62}px`, textAlign: "center" }}>
        <div className="subtle" style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontSize: 12 }}>
          {label}
        </div>
        <div style={{ fontSize: 48, fontWeight: 800, letterSpacing: "-0.05em" }}>{clamped}</div>
        {subtitle ? <div className="subtle">{subtitle}</div> : null}
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
