import PropTypes from "prop-types";

function getStatus(updatedAt, intervalMs = 30000) {
  if (!updatedAt) return "disconnected";
  const elapsed = Date.now() - updatedAt.getTime();
  if (elapsed < intervalMs * 1.5) return "connected";
  if (elapsed < intervalMs * 3) return "stale";
  return "disconnected";
}

const LABELS = {
  connected: "연결됨",
  stale: "지연 중",
  disconnected: "연결 끊김",
};

export default function ConnectionStatus({ updatedAt, intervalMs = 30000 }) {
  const status = getStatus(updatedAt, intervalMs);

  return (
    <span className={`connection-status connection-status--${status}`} role="status" aria-label={`Connection: ${status}`}>
      <span className="status-dot" />
      {LABELS[status]}
    </span>
  );
}

ConnectionStatus.propTypes = {
  updatedAt: PropTypes.instanceOf(Date),
  intervalMs: PropTypes.number,
};
