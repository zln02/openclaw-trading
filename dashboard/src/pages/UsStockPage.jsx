import { Globe, TrendingUp, Wallet, DollarSign, ShieldAlert, Newspaper } from "lucide-react";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import TradeTable from "../components/TradeTable";
import {
  getUsPositions,
  getUsTrades,
  getUsMarket,
  getUsFx,
  getUsRealtimePrice,
  getUsRealtimeAlt,
  getUsRealtimeNews,
} from "../api";

const fmt = (n) => n != null ? Number(n).toLocaleString() : "—";
const pct = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—";

const TRADE_COLS = [
  { key: "created_at", label: "시간", render: (_v, row) => (row.created_at || row.timestamp || row.executed_at || "").slice(5, 16) },
  { key: "trade_type", label: "구분", render: (_v, row) => {
    const side = row.trade_type || row.action || row.side || "";
    return (
      <span className={side === "BUY" ? "text-emerald-400 font-medium" : side === "SELL" ? "text-red-400 font-medium" : "text-gray-400"}>{side || "—"}</span>
    );
  }},
  { key: "symbol", label: "종목", render: (v) => <span className="font-medium">{v}</span> },
  { key: "price", label: "가격", render: (_v, row) => `$${fmt(row.price ?? row.executed_price)}` },
  { key: "quantity", label: "수량", render: (_v, row) => row.quantity ?? row.qty ?? "—" },
  { key: "score", label: "스코어" },
  { key: "reason", label: "사유", render: (_v, row) => <span className="text-gray-400 text-xs max-w-[180px] truncate block">{row.reason || row.strategy || ""}</span> },
];

const US_REALTIME_SYMBOL = "AAPL";
const fetchUsRtPrice = () => getUsRealtimePrice(US_REALTIME_SYMBOL);
const fetchUsRtAlt = () => getUsRealtimeAlt(US_REALTIME_SYMBOL);
const fetchUsRtNews = () => getUsRealtimeNews(US_REALTIME_SYMBOL, 10);

export default function UsStockPage() {
  const { data: positionsResp } = usePolling(getUsPositions, 30000);
  const { data: trades } = usePolling(getUsTrades, 60000);
  const { data: market } = usePolling(getUsMarket, 60000);
  const { data: fx } = usePolling(getUsFx, 120000);
  const { data: rtPrice } = usePolling(fetchUsRtPrice, 5000);
  const { data: rtAlt } = usePolling(fetchUsRtAlt, 60000);
  const { data: rtNews } = usePolling(fetchUsRtNews, 120000);

  const regime = market?.regime;
  const openPositions = Array.isArray(positionsResp?.positions) ? positionsResp.positions : [];
  const summary = positionsResp?.summary || {};
  const newsItems = Array.isArray(rtNews?.items) ? rtNews.items : [];

  const totalPnlFallback = openPositions.reduce((sum, p) => {
    if (!p.price || !p.current_price) return sum;
    return sum + (p.current_price - p.price) * (p.quantity || 0);
  }, 0);
  const totalPnl = summary?.total_pnl_usd ?? totalPnlFallback;

  const regimeColor = {
    BULL: "badge-green", CORRECTION: "badge-yellow",
    RECOVERY: "badge-blue", BEAR: "badge-red",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Globe className="w-7 h-7 text-violet-400" />
        <h1 className="text-xl font-bold">US 주식 대시보드</h1>
        {regime && (
          <span className={`ml-auto text-xs px-2 py-0.5 rounded ${regimeColor[regime.regime] || "badge-yellow"}`}>
            {regime.regime}
          </span>
        )}
      </div>

      {/* Market Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard
          label="SPY"
          value={regime?.spy_price ? `$${fmt(regime.spy_price)}` : "—"}
          sub={regime?.spy_ma200 ? `200MA: $${fmt(regime.spy_ma200)}` : null}
          trend={regime?.spy_above_200ma ? "up" : "down"}
          icon={TrendingUp}
        />
        <StatCard
          label="VIX"
          value={regime?.vix ?? "—"}
          trend={regime?.vix > 25 ? "up" : regime?.vix < 18 ? "down" : null}
          icon={ShieldAlert}
        />
        <StatCard label="보유 종목" value={openPositions.length} icon={Wallet} />
        <StatCard
          label="미실현 손익"
          value={`$${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(1)}`}
          trend={totalPnl > 0 ? "up" : totalPnl < 0 ? "down" : null}
          icon={DollarSign}
        />
        <StatCard
          label="환율"
          value={fx?.usdkrw ? `₩${fmt(fx.usdkrw)}` : "—"}
          icon={DollarSign}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label={`${US_REALTIME_SYMBOL} 실시간`} value={rtPrice?.price ? `$${fmt(rtPrice.price)}` : "—"} />
        <StatCard
          label="검색 트렌드"
          value={rtAlt?.search_trend_7d ?? "—"}
          trend={rtAlt?.search_trend_7d > 60 ? "up" : rtAlt?.search_trend_7d < 30 ? "down" : null}
        />
        <StatCard
          label="소셜 감정"
          value={rtAlt?.sentiment_score ?? "—"}
          trend={rtAlt?.sentiment_score > 0 ? "up" : rtAlt?.sentiment_score < 0 ? "down" : null}
          icon={ShieldAlert}
        />
        <StatCard label="소셜 멘션" value={rtAlt?.social_mentions_24h ?? "—"} />
      </div>

      {/* Open Positions */}
      {openPositions.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-medium text-gray-400 mb-3">보유 포지션 (모의투자)</h3>
          <div className="space-y-2">
            {openPositions.map((p, i) => {
              const entry = Number(p.price);
              const cur = Number(p.current_price || entry);
              const pnlPct = entry > 0 ? ((cur - entry) / entry * 100) : 0;
              const pnlUsd = (cur - entry) * (p.quantity || 0);
              return (
                <div key={i} className="flex items-center justify-between py-2 px-3 bg-gray-800/30 rounded-lg text-sm">
                  <div>
                    <span className="font-medium">{p.symbol}</span>
                    <span className="text-xs text-gray-500 ml-2">{p.quantity}주 × ${entry.toFixed(2)}</span>
                  </div>
                  <div className="text-right">
                    <div>${cur.toFixed(2)}</div>
                    <div className={`text-xs ${pnlPct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {pct(pnlPct)} (${pnlUsd >= 0 ? "+" : ""}{pnlUsd.toFixed(1)})
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="card">
        <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
          <Newspaper className="w-4 h-4" /> US 실시간 뉴스
        </h3>
        <ul className="space-y-1 text-xs text-gray-400 max-h-32 overflow-y-auto">
          {newsItems.slice(0, 6).map((row, i) => (
            <li key={i} className="truncate">• {row.headline || row.title}</li>
          ))}
        </ul>
      </div>

      {/* Trades */}
      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-3">최근 거래</h3>
        <TradeTable trades={Array.isArray(trades) ? trades : []} columns={TRADE_COLS} />
      </div>
    </div>
  );
}
