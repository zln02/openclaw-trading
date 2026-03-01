import { Building2, Wallet, Clock, TrendingUp, Activity, BarChart2 } from "lucide-react";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import ScoreGauge from "../components/ScoreGauge";
import TradeTable from "../components/TradeTable";
import TvWidget from "../components/TvWidget";

// symbol-overview: 지수/종목을 개별 미니차트로 표시 (market-overview 대비 KRX 호환성 우수)
const TV_KR_CONFIG = {
  symbols: [
    ["KOSPI",   "KRX:KOSPI|3M"],
    ["KOSDAQ",  "KRX:KOSDAQ|3M"],
    ["삼성전자", "KRX:A005930|3M"],
    ["SK하이닉스","KRX:A000660|3M"],
  ],
  chartOnly: false,
  colorTheme: "dark",
  locale: "kr",
  autosize: true,
  showVolume: false,
  changeMode: "price-and-percent",
  chartType: "area",
  lineWidth: 2,
  dateRanges: ["1d|1", "1m|30", "3m|60", "12m|1D"],
};

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
  const { data: portfolio }  = usePolling(getKrPortfolio, 15000);
  const { data: trades }     = usePolling(getKrTrades, 20000);
  const { data: system }     = usePolling(getKrSystem, 30000);
  const { data: topStocks }  = usePolling(getKrTop, 60000);

  const summary   = portfolio?.summary || {};
  const positions = portfolio?.open_positions || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="w-7 h-7 text-blue-400" />
          <h1 className="text-2xl font-bold text-text-primary">KR 주식 대시보드</h1>
        </div>
        {system?.last_cron && (
          <span className="text-xs text-text-secondary flex items-center gap-1 bg-card/50 px-3 py-1 rounded-full border border-border">
            <Clock className="w-3 h-3" /> {system.last_cron}
          </span>
        )}
      </div>

      {/* Score Row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <ScoreGauge score={composite?.total ?? 0} label="KR 종합 점수" />
        <StatCard
          label="KOSPI"
          value={composite?.kospi ?? "—"}
          icon={BarChart2}
          size="large"
          tooltip="KOSPI 지수 레벨"
        />
        <StatCard
          label="KOSDAQ"
          value={composite?.kosdaq ?? "—"}
          icon={Activity}
          size="large"
          tooltip="KOSDAQ 지수 레벨"
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
          icon={Building2}
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
          {(summary?.open_count ?? 0) === 0 && !summary?.krw_balance ? (
            <div className="py-6 text-center">
              <div className="text-text-secondary text-sm">모의투자 대기 중</div>
              <div className="text-text-muted text-xs mt-1">키움 API 연결 또는 장 개시 후 업데이트</div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-text-secondary mb-1">예수금</div>
                <div className="font-mono font-medium">₩{fmt(summary?.krw_balance)}</div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">총 평가</div>
                <div className="font-mono font-medium">₩{fmt(summary?.total_eval)}</div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">미실현 손익</div>
                <div className={`font-mono font-medium ${summary?.unrealized_pnl >= 0 ? "profit-text" : "loss-text"}`}>
                  ₩{fmt(summary?.unrealized_pnl)}
                </div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">보유 종목</div>
                <div className="font-mono font-medium">{summary?.open_count ?? 0}개</div>
              </div>
            </div>
          )}
        </div>

        {/* Top Stocks */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> TOP 종목
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
                <div className="text-text-secondary text-sm">장 마감</div>
                <div className="text-text-muted text-xs mt-1">다음 스캔: 내일 08:00 KST</div>
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
                  {["종목", "수량", "진입가", "현재가", "수익률"].map((h) => (
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
                    <td className="text-right py-3 px-3 font-mono">₩{fmt(pos.price)}</td>
                    <td className="text-right py-3 px-3 font-mono">₩{fmt(pos.current_price ?? pos.price)}</td>
                    <td className={`text-right py-3 px-3 font-mono ${pos.pnl_pct >= 0 ? "profit-text" : "loss-text"}`}>
                      {pct(pos.pnl_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TradingView — KR 지수 & 주요 종목 */}
      <div className="card p-0 overflow-hidden">
        <div className="px-4 pt-4 pb-2 border-b border-border">
          <h3 className="text-sm font-medium text-text-primary">KR 시장 — 실시간 지수 & 종목</h3>
          <p className="text-xs text-text-secondary mt-0.5">KOSPI · KOSDAQ · 삼성전자 · SK하이닉스 — TradingView 제공</p>
        </div>
        <TvWidget widgetType="symbol-overview" config={TV_KR_CONFIG} height={340} />
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
              label="키움 연동"
              value={system.kiwoom_ok ? "정상" : "대기"}
              trend={system.kiwoom_ok ? "up" : "warning"}
              size="compact"
              tooltip="키움증권 API 연결 상태 (모의투자)"
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
