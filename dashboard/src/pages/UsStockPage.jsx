import { Globe, Wallet, Clock, TrendingUp, BarChart2, Activity } from "lucide-react";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import ScoreGauge from "../components/ScoreGauge";
import TradeTable from "../components/TradeTable";
import TvWidget from "../components/TvWidget";

const TV_US_OVERVIEW_CONFIG = {
  colorTheme: "dark",
  dateRange: "3M",
  showChart: true,
  locale: "en",
  isTransparent: false,
  showSymbolLogo: true,
  showFloatingTooltip: false,
  tabs: [
    {
      title: "US Indices",
      symbols: [
        { s: "FOREXCOM:SPXUSD", d: "S&P 500" },
        { s: "FOREXCOM:NSXUSD", d: "NASDAQ 100" },
        { s: "FOREXCOM:DJI",    d: "Dow Jones" },
      ],
    },
    {
      title: "ETFs",
      symbols: [
        { s: "AMEX:SPY",    d: "SPY" },
        { s: "NASDAQ:QQQ",  d: "QQQ" },
        { s: "AMEX:IWM",    d: "IWM (Russell)" },
        { s: "NASDAQ:TQQQ", d: "TQQQ (3x)" },
      ],
    },
    {
      title: "Sectors",
      symbols: [
        { s: "AMEX:XLK",  d: "Technology" },
        { s: "AMEX:XLF",  d: "Financials" },
        { s: "AMEX:XLE",  d: "Energy" },
        { s: "AMEX:XLV",  d: "Health Care" },
      ],
    },
  ],
};

const TV_TICKER_CONFIG = {
  symbols: [
    { proName: "FOREXCOM:SPXUSD", title: "S&P 500" },
    { proName: "FOREXCOM:NSXUSD", title: "NASDAQ 100" },
    { proName: "AMEX:SPY",        title: "SPY" },
    { proName: "NASDAQ:QQQ",      title: "QQQ" },
    { proName: "BITSTAMP:BTCUSD", title: "Bitcoin" },
    { proName: "FX_IDC:USDKRW",   title: "USD/KRW" },
  ],
  showSymbolLogo: true,
  isTransparent: false,
  displayMode: "adaptive",
  colorTheme: "dark",
  locale: "en",
};

const fmt = (n) => n != null ? Number(n).toLocaleString() : "—";
const pct = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—";

const TRADE_COLS = [
  { key: "timestamp", label: "시간", render: (v) => v?.slice(5, 16) },
  { key: "symbol", label: "종목", render: (v) => <span className="font-mono">{v}</span> },
  { key: "action", label: "구분", render: (v) => (
    <span className={v === "BUY" ? "profit-text" : v === "SELL" ? "loss-text" : "text-text-secondary"}>{v}</span>
  )},
  { key: "price", label: "가격", render: (v) => <span className="font-mono">${fmt(v)}</span> },
  { key: "quantity", label: "수량", render: (v) => <span className="font-mono">{fmt(v)}</span> },
  { key: "pnl_usd", label: "P&L", render: (v) => (
    <span className={v > 0 ? "profit-text" : v < 0 ? "loss-text" : "text-text-secondary"}>
      ${fmt(v)}
    </span>
  )},
];

async function apiFetch(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

const getUsComposite = () => apiFetch("/api/us/composite");
const getUsPortfolio  = () => apiFetch("/api/us/portfolio");
const getUsTrades     = () => apiFetch("/api/us/trades");
const getUsSystem     = () => apiFetch("/api/us/system");
const getUsTop        = () => apiFetch("/api/us/top");

export default function UsStockPage() {
  const { data: composite } = usePolling(getUsComposite, 10000);
  const { data: portfolio }  = usePolling(getUsPortfolio, 15000);
  const { data: trades }     = usePolling(getUsTrades, 20000);
  const { data: system }     = usePolling(getUsSystem, 30000);
  const { data: topStocks }  = usePolling(getUsTop, 60000);

  const summary   = portfolio?.summary || {};
  const positions = portfolio?.open_positions || [];

  return (
    <div className="space-y-6">
      {/* Ticker Tape — 미국 주요 지수 실시간 */}
      <div className="card p-0 overflow-hidden rounded-lg">
        <TvWidget widgetType="ticker-tape" config={TV_TICKER_CONFIG} height={56} />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Globe className="w-7 h-7 text-emerald-400" />
          <h1 className="text-2xl font-bold text-text-primary">US 주식 대시보드</h1>
        </div>
        {system?.last_cron && (
          <span className="text-xs text-text-secondary flex items-center gap-1 bg-card/50 px-3 py-1 rounded-full border border-border">
            <Clock className="w-3 h-3" /> {system.last_cron}
          </span>
        )}
      </div>

      {/* Score Row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <ScoreGauge score={composite?.total ?? 0} label="US 종합 점수" />
        <StatCard
          label="SPY"
          value={composite?.spy ?? "—"}
          icon={BarChart2}
          size="large"
          tooltip="S&P 500 ETF 모멘텀 점수"
        />
        <StatCard
          label="QQQ"
          value={composite?.qqq ?? "—"}
          icon={Activity}
          size="large"
          tooltip="NASDAQ 100 ETF 모멘텀 점수"
        />
        <StatCard
          label="시장 추세"
          value={composite?.trend ?? "—"}
          trend={composite?.trend === "UP" ? "up" : composite?.trend === "DOWN" ? "down" : null}
          icon={TrendingUp}
          tooltip="전체 시장 방향성"
        />
        <StatCard
          label="시장 심리"
          value={composite?.sentiment ?? "—"}
          trend={composite?.sentiment > 0 ? "up" : composite?.sentiment < 0 ? "down" : null}
          icon={Globe}
          tooltip="투자자 심리 지수"
        />
      </div>

      {/* Portfolio & Top Stocks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Portfolio Summary */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Wallet className="w-4 h-4" /> 포트폴리오 요약
            </h3>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-text-secondary mb-1">가용 자본</div>
              <div className="font-mono font-medium">${fmt(summary?.usd_balance)}</div>
            </div>
            <div>
              <div className="text-text-secondary mb-1">총 평가</div>
              <div className="font-mono font-medium">${fmt(summary?.total_current)}</div>
            </div>
            <div>
              <div className="text-text-secondary mb-1">미실현 손익</div>
              <div className={`font-mono font-medium ${summary?.unrealized_pnl >= 0 ? "profit-text" : "loss-text"}`}>
                ${fmt(summary?.unrealized_pnl)}
              </div>
            </div>
            <div>
              <div className="text-text-secondary mb-1">보유 종목</div>
              <div className="font-mono font-medium">{summary?.open_count ?? 0}개</div>
            </div>
          </div>
        </div>

        {/* Top Stocks */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> TOP 모멘텀 종목
            </h3>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {(topStocks ?? []).length > 0 ? (
              topStocks.slice(0, 6).map((stock) => (
                <div key={stock.id ?? stock.symbol} className="flex items-center justify-between text-sm">
                  <span className="font-mono font-medium">{stock.symbol}</span>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-text-secondary">Score {stock.score}</span>
                    <span className={stock.ret_5d >= 0 ? "profit-text" : "loss-text"}>
                      5d {pct(stock.ret_5d)}
                    </span>
                    <span className="text-text-muted">
                      20d {pct(stock.ret_20d)}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-6">
                <div className="text-text-secondary text-sm">스캔 대기 중</div>
                <div className="text-text-muted text-xs mt-1">다음 스캔: 22:30 KST (프리마켓)</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Open Positions */}
      {positions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary">보유 포지션</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["종목", "수량", "진입가", "현재가", "수익률", "P&L"].map((h) => (
                    <th key={h} className={`py-3 px-3 text-xs text-text-secondary font-medium uppercase tracking-wide ${h === "종목" ? "text-left" : "text-right"}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.slice(0, 5).map((pos) => (
                  <tr key={pos.id} className="border-b border-border/50 hover:bg-card/30 transition-colors">
                    <td className="py-3 px-3 font-mono">{pos.symbol}</td>
                    <td className="text-right py-3 px-3">{fmt(pos.quantity)}</td>
                    <td className="text-right py-3 px-3 font-mono">${fmt(pos.price)}</td>
                    <td className="text-right py-3 px-3 font-mono">${fmt(pos.current_price)}</td>
                    <td className={`text-right py-3 px-3 font-mono ${pos.pnl_pct >= 0 ? "profit-text" : "loss-text"}`}>
                      {pct(pos.pnl_pct)}
                    </td>
                    <td className={`text-right py-3 px-3 font-mono ${pos.pnl_usd >= 0 ? "profit-text" : "loss-text"}`}>
                      ${fmt(pos.pnl_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TradingView — US 지수 & ETF Market Overview */}
      <div className="card p-0 overflow-hidden">
        <div className="px-4 pt-4 pb-2 border-b border-border">
          <h3 className="text-sm font-medium text-text-primary">US 시장 — 실시간 지수 & ETF</h3>
          <p className="text-xs text-text-secondary mt-0.5">S&P 500 · NASDAQ · Dow Jones · ETF · 섹터 — TradingView 제공</p>
        </div>
        <TvWidget widgetType="market-overview" config={TV_US_OVERVIEW_CONFIG} height={440} />
      </div>

      {/* System Status */}
      {system && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary">시스템 상태</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="CPU"
              value={`${system.cpu ?? 0}%`}
              size="compact"
              tooltip="시스템 CPU 사용률"
            />
            <StatCard
              label="메모리"
              value={`${system.mem_pct ?? 0}%`}
              size="compact"
              tooltip="시스템 메모리 사용률"
            />
            <StatCard
              label="디스크"
              value={`${system.disk_pct ?? 0}%`}
              size="compact"
              tooltip="디스크 사용률"
            />
            <StatCard
              label="브로커 연동"
              value={system.alpaca_ok ? "정상" : "DRY-RUN"}
              trend={system.alpaca_ok ? "up" : "warning"}
              sub={system.alpaca_ok ? null : "시뮬레이션 모드"}
              size="compact"
              tooltip="Alpaca 브로커 API (DRY-RUN = 실제 주문 없음)"
            />
          </div>
        </div>
      )}

      {/* Recent Trades */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-text-primary">최근 거래 기록</h3>
        </div>
        <TradeTable trades={trades?.slice(0, 10) || []} columns={TRADE_COLS} />
      </div>
    </div>
  );
}
