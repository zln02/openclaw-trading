const API_BASE = import.meta.env.VITE_API_URL || "";

export const apiStatus = {
  lastSuccess: null,
  errorCount: 0,
  latency: 0,
};

async function fetchJSON(path) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  const start = performance.now();
  try {
    const res = await fetch(`${API_BASE}${path}`, { signal: controller.signal, credentials: 'include' });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const json = await res.json();
    apiStatus.lastSuccess = new Date();
    apiStatus.latency = Math.round(performance.now() - start);
    apiStatus.errorCount = 0;
    return json;
  } catch (err) {
    apiStatus.errorCount += 1;
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/** 네트워크/API 오류 시 null 반환 (폴링에 유용) */
async function fetchJSONSafe(path) {
  try {
    return await fetchJSON(path);
  } catch {
    return null;
  }
}

// BTC
export const getBtcComposite = () => fetchJSON("/api/btc/composite");
export const getBtcPortfolio = () => fetchJSON("/api/btc/portfolio");
export const getBtcTrades = () => fetchJSON("/api/trades?limit=20");
export const getBtcLiveActivity = () => fetchJSONSafe("/api/btc/live-activity?limit=20");
export const getBtcNews = () => fetchJSON("/api/news");
export const getBtcCandles = (interval = "minute5", count = 100) =>
  fetchJSON(`/api/candles?interval=${interval}&count=${count}`);
export const getBtcFilters = () => fetchJSONSafe("/api/btc/filters");

// KR Stocks
export const getKrComposite = () => fetchJSONSafe("/api/kr/composite");
export const getKrPortfolio = () => fetchJSON("/api/kr/portfolio");
export const getKrTop = () => fetchJSONSafe("/api/kr/top");
export const getKrTrades = (limit = 50, action = null, hours = null) => {
  let url = `/api/kr/trades?limit=${limit}`;
  if (action) url += `&action=${encodeURIComponent(action)}`;
  if (hours) url += `&hours=${hours}`;
  return fetchJSONSafe(url);
};
export const getKrPositions = () => fetchJSONSafe("/api/kr/positions");
export const getKrDailyPnl = (days = 7) => fetchJSONSafe(`/api/stocks/daily-pnl?days=${days}`);
export const getStockPortfolio = () => fetchJSON("/api/stocks/portfolio");
export const getStockTrades = () => fetchJSON("/api/stocks/trades?limit=20");
export const getStockStrategy = () => fetchJSON("/api/stocks/strategy");
export const getStockChart = (code, interval = "1d") =>
  fetchJSONSafe(`/api/stocks/chart/${encodeURIComponent(code)}?interval=${interval}`);
export const getStockIndicators = (code) =>
  fetchJSONSafe(`/api/stocks/indicators/${encodeURIComponent(code)}`);
export const getStockLogs = (source = "all") => fetchJSONSafe(`/api/stocks/logs?source=${source}`);

// US Stocks
export const getUsComposite = () => fetchJSONSafe("/api/us/composite");
export const getUsPortfolio = () => fetchJSONSafe("/api/us/portfolio");
export const getUsPositions = () => fetchJSON("/api/us/positions");
export const getUsTrades = () => fetchJSON("/api/us/trades");
export const getUsMarket = () => fetchJSON("/api/us/market");
export const getUsFx = () => fetchJSONSafe("/api/us/fx");
export const getUsChart = (symbol, period = "3mo") =>
  fetchJSONSafe(`/api/us/chart/${encodeURIComponent(symbol)}?period=${encodeURIComponent(period)}`);

// System / Risk
export const getRiskPortfolio = () => fetchJSONSafe("/api/risk/portfolio");

// Health
export const getHealth = () => fetchJSON("/health");
