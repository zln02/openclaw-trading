export function sma(series, period, sourceField = "close") {
  if (!Array.isArray(series) || series.length === 0 || period <= 0) return [];
  const out = [];
  let sum = 0;
  const window = [];
  for (const row of series) {
    const value = Number(row?.[sourceField] ?? row?.value ?? row?.close ?? 0);
    if (!Number.isFinite(value)) continue;
    window.push(value);
    sum += value;
    if (window.length > period) sum -= window.shift();
    if (window.length === period) {
      out.push({ time: row.time, value: sum / period });
    }
  }
  return out;
}
