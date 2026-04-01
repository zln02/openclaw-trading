/**
 * Signal strength → CSS color variable
 * Single source of truth used by MetricRow, ScoreRadial, BtcPage
 */
export function getSignalColor(value) {
  if (value <= 30) return "var(--color-loss)";
  if (value <= 70) return "var(--color-warning)";
  return "var(--color-profit)";
}
