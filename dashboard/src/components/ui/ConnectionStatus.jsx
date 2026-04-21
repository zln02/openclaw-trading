import PropTypes from "prop-types";
import { useLang } from "../../hooks/useLang";

function getStatus(updatedAt, intervalMs = 30000) {
  if (!updatedAt) return "disconnected";
  const elapsed = Date.now() - updatedAt.getTime();
  if (elapsed < intervalMs * 1.5) return "connected";
  if (elapsed < intervalMs * 3) return "stale";
  return "disconnected";
}

export default function ConnectionStatus({ updatedAt, intervalMs = 30000 }) {
  const { t } = useLang();
  const status = getStatus(updatedAt, intervalMs);
  const LABELS = {
    connected: t("연결됨"),
    stale: t("지연 중"),
    disconnected: t("연결 끊김"),
  };

  return (
    <span className={`connection-status connection-status--${status}`} role="status" aria-label={`${t("연결 상태")}: ${LABELS[status]}`}>
      <span className="status-dot" />
      {LABELS[status]}
    </span>
  );
}

ConnectionStatus.propTypes = {
  updatedAt: PropTypes.instanceOf(Date),
  intervalMs: PropTypes.number,
};
