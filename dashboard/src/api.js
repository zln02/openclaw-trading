const API_BASE = import.meta.env.VITE_API_URL || "";

async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// BTC
export const getBtcComposite = () => fetchJSON("/api/btc/composite");
export const getBtcPortfolio = () => fetchJSON("/api/btc/portfolio");
export const getBtcStats = () => fetchJSON("/api/stats");
export const getBtcTrades = () => fetchJSON("/api/trades?limit=20");
export const getBtcNews = () => fetchJSON("/api/news");
export const getBtcSystem = () => fetchJSON("/api/system");
export const getBtcCandles = (interval = "minute5", count = 100) =>
  fetchJSON(`/api/candles?interval=${interval}&count=${count}`);
export const getBtcRealtimeNews = (currencies = "BTC", limit = 10) =>
  fetchJSON(`/api/realtime/news?currencies=${encodeURIComponent(currencies)}&limit=${limit}`);
export const getBtcRealtimeOrderbook = (market = "upbit", symbol = "KRW-BTC") =>
  fetchJSON(`/api/realtime/orderbook?market=${encodeURIComponent(market)}&symbol=${encodeURIComponent(symbol)}`);
export const getBtcRealtimeAlt = (symbol = "BTC") =>
  fetchJSON(`/api/realtime/alt/${encodeURIComponent(symbol)}`);
export const getBtcRealtimePrice = (symbol = "KRW-BTC", market = "btc") =>
  fetchJSON(`/api/realtime/price/${encodeURIComponent(symbol)}?market=${encodeURIComponent(market)}`);

// KR Stocks
export const getKrPortfolio = () => fetchJSON("/api/kr/portfolio");
export const getStockOverview = () => fetchJSON("/api/stocks/overview");
export const getStockPortfolio = () => fetchJSON("/api/stocks/portfolio");
export const getStockTrades = () => fetchJSON("/api/stocks/trades?limit=20");
export const getStockMarket = () => fetchJSON("/api/stocks/market-summary");
export const getStockStrategy = () => fetchJSON("/api/stocks/strategy");
export const getStockRealtimePrice = (code) => fetchJSON(`/api/stocks/realtime/price/${encodeURIComponent(code)}`);
export const getStockRealtimeOrderbook = (code) => fetchJSON(`/api/stocks/realtime/orderbook/${encodeURIComponent(code)}`);
export const getStockRealtimeAlt = (symbol) => fetchJSON(`/api/stocks/realtime/alt/${encodeURIComponent(symbol)}`);

// US Stocks
export const getUsPositions = () => fetchJSON("/api/us/positions");
export const getUsTrades = () => fetchJSON("/api/us/trades");
export const getUsMarket = () => fetchJSON("/api/us/market");
export const getUsFx = () => fetchJSON("/api/us/fx");
export const getUsRealtimeNews = (symbol = "BTC", limit = 10) =>
  fetchJSON(`/api/us/realtime/news?symbol=${encodeURIComponent(symbol)}&limit=${limit}`);
export const getUsRealtimePrice = (symbol) => fetchJSON(`/api/us/realtime/price/${encodeURIComponent(symbol)}`);
export const getUsRealtimeAlt = (symbol) => fetchJSON(`/api/us/realtime/alt/${encodeURIComponent(symbol)}`);

// Health
export const getHealth = () => fetchJSON("/health");
