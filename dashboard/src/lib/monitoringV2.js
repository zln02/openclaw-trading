export function buildPnLCurve(equitySeries = []) {
  const rows = Array.isArray(equitySeries) ? equitySeries : [];
  if (!rows.length) return [];

  const first = Number(rows[0].equity || rows[0].value || 0);
  if (!first) return [];

  return rows.map((r) => {
    const equity = Number(r.equity || r.value || 0);
    const pnlPct = first > 0 ? ((equity / first) - 1) * 100 : 0;
    return {
      ts: r.ts || r.time || r.date,
      equity,
      pnlPct,
    };
  });
}

export function computeVarGauge(var95 = 0, varLimit = 0.025) {
  const v = Math.abs(Number(var95) || 0);
  const limit = Math.abs(Number(varLimit) || 0.025);
  const ratio = limit > 0 ? v / limit : 0;

  let level = "OK";
  if (ratio >= 1.3) level = "DANGER";
  else if (ratio >= 1.0) level = "WARNING";

  return {
    var95: v,
    varLimit: limit,
    utilization: ratio,
    level,
  };
}

export function computeDrawdownHeatmap(equitySeries = [], bucketSize = 5) {
  const curve = buildPnLCurve(equitySeries);
  if (!curve.length) return [];

  const buckets = [];
  for (let i = 0; i < curve.length; i += Math.max(1, bucketSize)) {
    const chunk = curve.slice(i, i + Math.max(1, bucketSize));
    const minPnl = Math.min(...chunk.map((x) => x.pnlPct));
    const maxPnl = Math.max(...chunk.map((x) => x.pnlPct));
    buckets.push({
      start: chunk[0].ts,
      end: chunk[chunk.length - 1].ts,
      minPnl,
      maxPnl,
      drawdown: minPnl,
    });
  }
  return buckets;
}

export function buildFactorRadar(exposure = {}) {
  return Object.entries(exposure || {}).map(([factor, value]) => ({
    factor,
    value: Number(value) || 0,
  }));
}

export function buildAllocationPie(weights = {}) {
  const entries = Object.entries(weights || {}).map(([name, weight]) => ({
    name,
    weight: Number(weight) || 0,
  }));

  const total = entries.reduce((acc, row) => acc + row.weight, 0);
  if (total <= 0) return [];

  return entries.map((row) => ({
    ...row,
    pct: (row.weight / total) * 100,
  }));
}
