import { BarChart3, TrendingUp, Wallet, ShieldAlert } from "lucide-react";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import TradeTable from "../components/TradeTable";
import {
  getStockOverview,
  getStockPortfolio,
  getStockTrades,
  getStockMarket,
  getStockStrategy,
  getStockRealtimePrice,
  getStockRealtimeOrderbook,
  getStockRealtimeAlt,
} from "../api";

const fmt = (n) => n != null ? Number(n).toLocaleString() : "—";
const pct = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—";

const TRADE_COLS = [
  { key: "created_at", label: "시간", render: (_v, row) => (row.created_at || row.timestamp || "").slice(5, 16) },
  {
    key: "trade_type",
    label: "구분",
    render: (_v, row) => {
      const side = row.trade_type || row.action || "";
      return (
        <span className={side === "BUY" ? "text-emerald-400 font-medium" : side === "SELL" ? "text-red-400 font-medium" : "text-gray-400"}>
          {side || "—"}
        </span>
      );
    },
  },
  { key: "symbol", label: "종목", render: (_v, row) => row.symbol || row.stock_code || row.code || "—" },
  { key: "price", label: "가격", render: (_v, row) => `₩${fmt(row.price ?? row.avg_price)}` },
  { key: "quantity", label: "수량", render: (_v, row) => row.quantity ?? row.qty ?? "—" },
  {
    key: "reason",
    label: "사유",
    render: (_v, row) => <span className="text-gray-400 text-xs max-w-[180px] truncate block">{row.reason || row.strategy || ""}</span>,
  },
];

const fetchKrRtPrice = () => getStockRealtimePrice("005930");
const fetchKrRtOrderbook = () => getStockRealtimeOrderbook("005930");
const fetchKrRtAlt = () => getStockRealtimeAlt("005930");

export default function KrStockPage() {
  const { data: overview } = usePolling(getStockOverview, 30000);
  const { data: portfolio } = usePolling(getStockPortfolio, 30000);
  const { data: trades } = usePolling(getStockTrades, 60000);
  const { data: market } = usePolling(getStockMarket, 60000);
  const { data: strategy } = usePolling(getStockStrategy, 120000);
  const { data: rtPrice } = usePolling(fetchKrRtPrice, 5000);
  const { data: rtOrderbook } = usePolling(fetchKrRtOrderbook, 5000);
  const { data: rtAlt } = usePolling(fetchKrRtAlt, 60000);

  const movers = Array.isArray(overview) ? overview : [];
  const portfolioData = portfolio || {};
  const positions = portfolioData.positions || [];
  const kospi = market?.kospi;
  const isOpen = portfolioData.is_market_open;
  const strategyData = strategy?.strategy || null;
  const candidates = strategyData?.candidates || [];
  const todayTrades = Array.isArray(trades) ? trades.length : 0;
  const topMover = movers[0] || null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BarChart3 className="w-7 h-7 text-blue-400" />
        <h1 className="text-xl font-bold">KR 주식 대시보드</h1>
        {isOpen != null && (
          <span className={`ml-auto text-xs px-2 py-0.5 rounded ${isOpen ? "badge-green" : "badge-red"}`}>
            {isOpen ? "장중" : "장 마감"}
          </span>
        )}
      </div>

      {/* Market Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="KOSPI"
          value={kospi?.price ? fmt(kospi.price) : "—"}
          sub={kospi?.change_pct ? pct(kospi.change_pct) : null}
          trend={kospi?.change_pct > 0 ? "up" : kospi?.change_pct < 0 ? "down" : null}
          icon={TrendingUp}
        />
        <StatCard label="보유 종목" value={positions.length} icon={Wallet} />
        <StatCard
          label="오늘 손익"
          value={portfolioData?.today_pnl != null ? `₩${fmt(portfolioData.today_pnl)}` : "—"}
          trend={portfolioData?.today_pnl > 0 ? "up" : portfolioData?.today_pnl < 0 ? "down" : null}
        />
        <StatCard
          label="오늘 매매"
          value={`${todayTrades}건`}
          icon={ShieldAlert}
          sub={topMover ? `변동상위: ${topMover.name || topMover.code}` : null}
          trend={topMover?.change > 0 ? "up" : topMover?.change < 0 ? "down" : null}
        />
      </div>

      {/* Realtime Phase 9 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="삼성전자 실시간" value={rtPrice?.price ? `₩${fmt(rtPrice.price)}` : "—"} />
        <StatCard
          label="호가 불균형"
          value={rtOrderbook?.imbalance ?? "—"}
          trend={rtOrderbook?.imbalance > 0 ? "up" : rtOrderbook?.imbalance < 0 ? "down" : null}
          sub={rtOrderbook?.source || null}
        />
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
      </div>

      {/* Strategy */}
      {strategyData && (
        <div className="card">
          <h3 className="text-sm font-medium text-gray-400 mb-3">오늘의 전략</h3>
          {candidates.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {candidates.slice(0, 8).map((c, i) => (
                <div key={i} className="bg-gray-800/50 rounded-lg p-3 text-sm">
                  <div className="font-medium text-white">{c.symbol || c.name}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {c.score ? `스코어: ${c.score}` : ""}
                    {c.sector ? ` · ${c.sector}` : ""}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-600 text-sm">전략 데이터 없음</div>
          )}
        </div>
      )}

      {/* Positions */}
      {positions.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-medium text-gray-400 mb-3">보유 포지션</h3>
          <div className="space-y-2">
            {positions.map((p, i) => {
              const entry = Number(p.avg_entry ?? p.entry_price ?? 0);
              const current = Number(p.current_price ?? p.price ?? 0);
              const pnlPct = p.pnl_pct ?? (entry > 0 ? ((current - entry) / entry) * 100 : 0);
              return (
                <div key={i} className="flex items-center justify-between py-2 px-3 bg-gray-800/30 rounded-lg text-sm">
                  <div>
                    <span className="font-medium">{p.symbol || p.code || p.name}</span>
                    <span className="text-xs text-gray-500 ml-2">{p.quantity}주</span>
                  </div>
                  <div className="text-right">
                    <div>₩{fmt(current)}</div>
                    <div className={`text-xs ${pnlPct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {pct(pnlPct)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Trades */}
      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-3">최근 거래</h3>
        <TradeTable trades={Array.isArray(trades) ? trades : []} columns={TRADE_COLS} />
      </div>
    </div>
  );
}
