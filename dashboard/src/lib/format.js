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
  return new Date(value).toLocaleString("ko-KR", {
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
