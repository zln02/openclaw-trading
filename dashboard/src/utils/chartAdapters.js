export function toUnixSeconds(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value > 1e12 ? Math.floor(value / 1000) : Math.floor(value);
  }
  const parsed = Date.parse(value || "");
  if (Number.isFinite(parsed)) {
    return Math.floor(parsed / 1000);
  }
  return null;
}

export function tradesToMarkers(
  trades,
  {
    timeFields = ["created_at", "timestamp", "time"],
    priceFields = ["price", "entry_price", "exit_price"],
    actionFields = ["action", "trade_type", "side"],
  } = {},
) {
  if (!Array.isArray(trades)) return [];
  const profit = readCssVar("--color-profit", "#00d4aa");
  const loss = readCssVar("--color-loss", "#ff4757");

  const markers = [];
  for (const row of trades) {
    if (!row) continue;
    const action = pickFirst(row, actionFields, "").toString().toUpperCase();
    if (action !== "BUY" && action !== "SELL") continue;

    const time = toUnixSeconds(pickFirst(row, timeFields));
    if (time == null) continue;

    const priceRaw = pickFirst(row, priceFields);
    const price = Number(priceRaw);

    markers.push({
      time,
      position: action === "BUY" ? "belowBar" : "aboveBar",
      color: action === "BUY" ? profit : loss,
      shape: action === "BUY" ? "arrowUp" : "arrowDown",
      text: Number.isFinite(price) && price > 0 ? `${action} ${formatPrice(price)}` : action,
    });
  }
  markers.sort((a, b) => a.time - b.time);
  return dedupeByTime(markers);
}

function pickFirst(obj, keys, fallback) {
  for (const key of keys) {
    if (obj[key] != null) return obj[key];
  }
  return fallback;
}

function readCssVar(name, fallback) {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function formatPrice(value) {
  if (value >= 1000) return Math.round(value).toLocaleString();
  return value.toFixed(2);
}

function dedupeByTime(markers) {
  const seen = new Set();
  const out = [];
  for (const m of markers) {
    const key = `${m.time}-${m.shape}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(m);
  }
  return out;
}
