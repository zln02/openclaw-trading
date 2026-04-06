import PropTypes from "prop-types";

const MAP = {
  RISK_ON: { bg: "rgba(34,197,94,0.16)", color: "var(--profit)", dot: "var(--profit)", pulse: "livePulse 1.5s infinite" },
  RISK_OFF: { bg: "rgba(239,68,68,0.16)", color: "var(--loss)", dot: "var(--loss)" },
  TRANSITION: { bg: "rgba(245,158,11,0.16)", color: "var(--warning)", dot: "var(--warning)" },
  CRISIS: { bg: "rgba(239,68,68,0.2)", color: "var(--loss)", dot: "var(--loss)" },
};

export default function StatusBadge({ status = "TRANSITION" }) {
  const key = String(status || "TRANSITION").toUpperCase();
  const tone = MAP[key] || MAP.TRANSITION;

  return (
    <span
      className="pill"
      role="status"
      aria-label={`Market regime: ${key}`}
      style={{
        background: tone.bg,
        color: tone.color,
        animation: key === "CRISIS" ? "crisisPulse 1.4s infinite" : "none",
      }}
    >
      <span className="status-dot" style={{ background: tone.dot, animation: tone.pulse || "none" }} />
      {key}
    </span>
  );
}

StatusBadge.propTypes = {
  status: PropTypes.string,
};
