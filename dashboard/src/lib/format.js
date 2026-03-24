export const krw = (value) =>
  value == null
    ? "—"
    : `₩${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export const usd = (value) =>
  value == null
    ? "—"
    : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export const pct = (value) =>
  value == null ? "—" : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;

export const compactTime = (value) => {
  if (!value) {
    return "—";
  }
  // DB timestamps are UTC but may lack timezone suffix — force UTC parsing
  const normalized = String(value).match(/[Z+\-]\d{2}:?\d{2}$|Z$/) ? value : `${value}Z`;
  return new Date(normalized).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const sparkline = (items = [], key = "value") =>
  (Array.isArray(items) ? items : []).map((item, index) => ({
    label: item?.label || item?.date || item?.time || `${index + 1}`,
    value: Number(item?.[key] ?? item ?? 0),
  }));

export const num = (value, digits = 0) =>
  value == null ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });

export const signed = (value, digits = 2) =>
  value == null ? "—" : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(digits)}`;

export const relativeTime = (value, now = Date.now()) => {
  if (!value) return "never";
  const normalized = String(value).match(/[Z+\-]\d{2}:?\d{2}$|Z$/) ? value : `${value}Z`;
  const diffMs = now - new Date(normalized).getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin <= 0) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  return `${Math.round(diffHour / 24)}d ago`;
};

export const marketTone = (value) => (Number(value || 0) >= 0 ? "profit" : "loss");

export const buildSparkline = (value = 0, delta = 0, points = 8) => {
  const current = Number(value || 0);
  const change = Number(delta || 0) / 100;
  const start = current / (1 + change || 1);
  const series = [];

  for (let index = 0; index < points; index += 1) {
    const ratio = index / (points - 1 || 1);
    const noise = Math.sin(index * 1.7) * current * 0.0025;
    series.push({ value: start + (current - start) * ratio + noise });
  }

  return series;
};
