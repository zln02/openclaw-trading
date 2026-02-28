import { Building2, Gauge, Wallet, Clock, Newspaper, TrendingUp, DollarSign } from "lucide-react";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import TradeTable from "../components/TradeTable";

const fmt = (n) => n != null ? Number(n).toLocaleString() : "—";
const pct = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—";

const TRADE_COLS = [
  { key: "timestamp", label: "시간", render: (v) => v?.slice(5, 16) },
  { key: "action", label: "구분", render: (v) => (
    <span className={v === "BUY" ? "profit-text" : v === "SELL" ? "loss-text" : "text-text-secondary"}>{v}</span>
  )},
  { key: "symbol", label: "종목", render: (v) => <span className="font-mono">{v}</span> },
  { key: "price", label: "가격", render: (v) => <span className="font-mono">₩{fmt(v)}</span> },
  { key: "quantity", label: "수량", render: (v) => <span className="font-mono">{fmt(v)}</span> },
  { key: "pnl_pct", label: "수익률", render: (v) => (
    <span className={v > 0 ? "profit-text" : v < 0 ? "loss-text" : "text-text-secondary"}>
      {pct(v)}
    </span>
  )},
];

async function apiFetch(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

const getKrComposite = () => apiFetch("/api/kr/composite");
const getKrPortfolio  = () => apiFetch("/api/kr/portfolio");
const getKrTrades     = () => apiFetch("/api/kr/trades");
const getKrSystem     = () => apiFetch("/api/kr/system");
const getKrTop        = () => apiFetch("/api/kr/top");

export default function KrStockPage() {
  const { data: composite } = usePolling(getKrComposite, 10000);
  const { data: portfolio } = usePolling(getKrPortfolio, 15000);
  const { data: trades } = usePolling(getKrTrades, 20000);
  const { data: system } = usePolling(getKrSystem, 30000);
  const { data: topStocks } = usePolling(getKrTop, 60000);

  const summary = portfolio?.summary || {};
  const positions = portfolio?.open_positions || [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Building2 className="w-8 h-8 text-accent" />
          <div>
            <h1 className="text-2xl font-bold text-text-primary">한국 주식</h1>
            <p className="text-text-secondary text-sm">KOSPI/KOSDAQ 실시간 모니터링</p>
          </div>
        </div>
        {system && (
          <div className="flex items-center space-x-4 text-xs text-text-secondary">
            <span>Kiwoom: {system.kiwoom_ok ? "🟢" : "🔴"}</span>
            <span>CPU: {system.cpu}%</span>
            <span>MEM: {system.mem_pct}%</span>
          </div>
        )}
      </div>

      {/* Composite Score */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="종합 점수"
          value={composite?.total || 0}
          sub={`KOSPI: ${composite?.kospi || 0} | KOSDAQ: ${composite?.kosdaq || 0}`}
          icon={Gauge}
          trend={composite?.trend === "UP" ? "up" : composite?.trend === "DOWN" ? "down" : null}
          tooltip="KOSPI/KOSDAQ 종합 시장 점수"
        />
        <StatCard
          label="거래량"
          value={composite?.volume || 0}
          sub="시장 거래량 지표"
          icon={TrendingUp}
          tooltip="전체 시장 거래량"
        />
        <StatCard
          label="시장 심리"
          value={composite?.sentiment || 0}
          sub="투자자 심리 지수"
          icon={Newspaper}
          tooltip="시장 참여자 심리 상태"
        />
      </div>

      {/* Portfolio Summary */}
      <div className="card">
        <div className="card-header">
          <Wallet className="w-5 h-5" />
          <h3>포트폴리오 요약</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="data-label">예수금</div>
            <div className="data-value">₩{fmt(summary?.krw_balance)}</div>
          </div>
          <div className="text-center">
            <div className="data-label">총 평가</div>
            <div className="data-value">₩{fmt(summary?.total_eval)}</div>
          </div>
          <div className="text-center">
            <div className="data-label">미실현 손익</div>
            <div className={`data-value ${summary?.unrealized_pnl >= 0 ? "profit-text" : "loss-text"}`}>
              ₩{fmt(summary?.unrealized_pnl)}
            </div>
          </div>
          <div className="text-center">
            <div className="data-label">보유 종목</div>
            <div className="data-value">{summary?.open_count || 0}개</div>
          </div>
        </div>
      </div>

      {/* Open Positions */}
      {positions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <DollarSign className="w-5 h-5" />
            <h3>보유 포지션</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3">종목</th>
                  <th className="text-right py-2 px-3">수량</th>
                  <th className="text-right py-2 px-3">진입가</th>
                  <th className="text-right py-2 px-3">현재가</th>
                  <th className="text-right py-2 px-3">수익률</th>
                </tr>
              </thead>
              <tbody>
                {positions.slice(0, 5).map((pos) => (
                  <tr key={pos.id} className="border-b border-border/50">
                    <td className="py-2 px-3 font-mono">{pos.symbol}</td>
                    <td className="text-right py-2 px-3">{fmt(pos.quantity)}</td>
                    <td className="text-right py-2 px-3">₩{fmt(pos.price)}</td>
                    <td className="text-right py-2 px-3">₩{fmt(pos.current_price ?? pos.price)}</td>
                    <td className={`text-right py-2 px-3 ${pos.pnl_pct >= 0 ? "profit-text" : "loss-text"}`}>
                      {pct(pos.pnl_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Trades */}
      <div className="card">
        <div className="card-header">
          <Clock className="w-5 h-5" />
          <h3>최근 거래</h3>
        </div>
        <TradeTable
          trades={trades?.slice(0, 10) || []}
          columns={TRADE_COLS}
        />
      </div>

      {/* Top Stocks */}
      {topStocks && topStocks.length > 0 && (
        <div className="card">
          <div className="card-header">
            <TrendingUp className="w-5 h-5" />
            <h3>TOP 종목</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {topStocks.slice(0, 9).map((stock) => (
              <div key={stock.id} className="p-3 border border-border rounded-lg">
                <div className="flex justify-between items-center">
                  <span className="font-mono font-semibold">{stock.symbol}</span>
                  <span className={`text-sm ${stock.ret_5d >= 0 ? "profit-text" : "loss-text"}`}>
                    {pct(stock.ret_5d)}
                  </span>
                </div>
                <div className="text-xs text-text-secondary mt-1">
                  Score: {stock.score} | 변동률: {pct(stock.ret_20d)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
