import { Bitcoin, Gauge, Wallet, Clock, Newspaper, TrendingUp, TrendingDown, Minus } from "lucide-react";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import ScoreGauge from "../components/ScoreGauge";
import TradeTable from "../components/TradeTable";
import TvWidget from "../components/TvWidget";

const TV_BTC_CONFIG = {
  symbol: "UPBIT:BTCKRW",
  interval: "60",
  timezone: "Asia/Seoul",
  theme: "dark",
  style: "1",
  locale: "kr",
  allow_symbol_change: true,
  hide_top_toolbar: false,
  hide_legend: false,
  hide_volume: false,
  support_host: "https://www.tradingview.com",
};
import {
  getBtcComposite,
  getBtcPortfolio,
  getBtcTrades,
  getBtcSystem,
  getBtcRealtimeAlt,
  getBtcRealtimeNews,
  getBtcRealtimeOrderbook,
  getBtcRealtimePrice,
} from "../api";

const fmt = (n) => n != null ? Number(n).toLocaleString() : "—";
const pct = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—";

const TRADE_COLS = [
  { key: "timestamp", label: "시간", render: (v) => v?.slice(5, 16) },
  { key: "action", label: "구분", render: (v) => {
    const u = String(v || "").toUpperCase();
    if (u === "BUY")  return <span className="badge-green">매수</span>;
    if (u === "SELL") return <span className="badge-red">매도</span>;
    return <span className="badge-yellow">{v}</span>;
  }},
  { key: "price", label: "가격", render: (v) => <span className="font-mono">₩{fmt(v)}</span> },
  { key: "pnl_pct", label: "수익률", render: (v) => (
    <span className={v > 0 ? "profit-text" : v < 0 ? "loss-text" : "text-text-secondary"}>
      {v != null ? pct(v) : "—"}
    </span>
  )},
  { key: "rsi", label: "RSI" },
  { key: "confidence", label: "신뢰도", render: (v) => (
    <span className="text-text-secondary">{v != null ? `${v}%` : "—"}</span>
  )},
  { key: "reason", label: "사유", render: (v) => (
    <span className="text-text-secondary text-xs max-w-[200px] truncate block">{v}</span>
  )},
];

const fetchBtcRtPrice = () => getBtcRealtimePrice("KRW-BTC", "btc");
const fetchBtcOrderbook = () => getBtcRealtimeOrderbook("upbit", "KRW-BTC");
const fetchBtcAlt = () => getBtcRealtimeAlt("BTC");
const fetchBtcNews = () => getBtcRealtimeNews("BTC", 10);

export default function BtcPage() {
  const { data: comp } = usePolling(getBtcComposite, 30000);
  const { data: port } = usePolling(getBtcPortfolio, 30000);
  const { data: trades } = usePolling(getBtcTrades, 60000);
  const { data: news } = usePolling(fetchBtcNews, 120000);
  const { data: sys } = usePolling(getBtcSystem, 60000);
  const { data: rtPrice } = usePolling(fetchBtcRtPrice, 5000);
  const { data: orderbook } = usePolling(fetchBtcOrderbook, 5000);
  const { data: alt } = usePolling(fetchBtcAlt, 60000);

  const score = comp?.composite;
  const summary = port?.summary || {};
  const position = (port?.open_positions || [])[0] || null;
  const priceNow = rtPrice?.price;
  const newsRows = Array.isArray(news?.items) ? news.items : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bitcoin className="w-7 h-7 text-amber-400" />
          <h1 className="text-2xl font-bold text-text-primary">BTC 대시보드</h1>
        </div>
        {sys?.last_cron && (
          <span className="text-xs text-text-secondary flex items-center gap-1 bg-card/50 px-3 py-1 rounded-full border border-border">
            <Clock className="w-3 h-3" /> {sys.last_cron}
          </span>
        )}
      </div>

      {/* Main Score & Price Row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <ScoreGauge score={score?.total ?? 0} />
        <StatCard 
          label="현재가" 
          value={`₩${fmt(priceNow)}`} 
          icon={Bitcoin}
          size="large"
          tooltip="실시간 BTC/KRW 가격"
        />
        <StatCard
          label="F&G 공포지수"
          value={comp?.fg_value ?? "—"}
          sub={comp?.fg_value != null ? (comp.fg_value < 30 ? "극공포" : comp.fg_value > 70 ? "탐욕" : "중립") : null}
          trend={comp?.fg_value < 40 ? "down" : comp?.fg_value > 60 ? "up" : null}
          icon={Gauge}
          tooltip="시장 심리 지수 (0-100)"
        />
        {/* 1시간 추세 — 방향 화살표 */}
        {(() => {
          const t = String(comp?.trend ?? "");
          const isUp   = t.includes("UP")   && !t.includes("DOWN");
          const isDown = t.includes("DOWN");
          const Icon   = isUp ? TrendingUp : isDown ? TrendingDown : Minus;
          const color  = isUp ? "text-profit" : isDown ? "text-loss" : "text-text-secondary";
          return (
            <div className="card p-4">
              <div className="data-label mb-3">1시간 추세</div>
              <div className="flex items-center gap-2">
                <Icon className={`w-6 h-6 ${color}`} />
                <span className={`font-mono font-bold text-xl ${color}`}>{t || "—"}</span>
              </div>
            </div>
          );
        })()}

        {/* 일봉 RSI — 게이지 바 */}
        <div className="card p-4">
          <div className="data-label mb-2">일봉 RSI</div>
          <div className={`data-value text-xl mb-3 ${
            comp?.rsi_d < 30 ? "text-profit" : comp?.rsi_d > 70 ? "text-loss" : "text-text-primary"
          }`}>
            {comp?.rsi_d ?? "—"}
          </div>
          {comp?.rsi_d != null && (
            <>
              <div className="relative w-full h-2 rounded-full overflow-hidden bg-card/50 border border-border/50">
                <div className="absolute inset-y-0 left-0 w-[30%] bg-profit/20" />
                <div className="absolute inset-y-0 right-0 w-[30%] bg-loss/20" />
                <div
                  className={`absolute top-0 bottom-0 w-1.5 rounded-full ${
                    comp.rsi_d < 30 ? "bg-profit" : comp.rsi_d > 70 ? "bg-loss" : "bg-amber-400"
                  }`}
                  style={{ left: `calc(${Math.min(Math.max(comp.rsi_d, 0), 100)}% - 3px)` }}
                />
              </div>
              <div className="flex justify-between text-xs text-text-muted mt-1">
                <span>과매도</span><span>중립</span><span>과매수</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Market Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="호가 스프레드"
          value={orderbook?.spread != null ? fmt(orderbook.spread) : "—"}
          sub={orderbook?.source || null}
          tooltip="매수-매가 호가 차이"
        />
        <StatCard
          label="호가 불균형"
          value={orderbook?.imbalance != null ? orderbook.imbalance : "—"}
          trend={orderbook?.imbalance > 0 ? "up" : orderbook?.imbalance < 0 ? "down" : null}
          tooltip="매수/매도 호가량 불균형"
        />
        <StatCard
          label="검색 트렌드"
          value={alt?.search_trend_7d ?? "—"}
          trend={alt?.search_trend_7d > 60 ? "up" : alt?.search_trend_7d < 30 ? "down" : null}
          tooltip="7일간 구글 검색 트렌드"
        />
        <StatCard
          label="대체데이터 감정"
          value={alt?.sentiment_score ?? "—"}
          trend={alt?.sentiment_score > 0 ? "up" : alt?.sentiment_score < 0 ? "down" : null}
          tooltip="소셜 미디어 감성 분석"
        />
      </div>

      {/* Score Breakdown */}
      {score && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary">복합 스코어 상세</h3>
          </div>
          <div className="grid grid-cols-3 md:grid-cols-9 gap-3">
            {[
              ["F&G", score.fg, "공포지수"],
              ["RSI", score.rsi, "상대강도"],
              ["BB", score.bb, "볼린저밴드"],
              ["Vol", score.vol, "거래량"],
              ["Trend", score.trend, "추세"],
              ["Fund", score.funding, "펀딩"],
              ["LS", score.ls, "롱숏"],
              ["OI", score.oi, "미결제약정"],
              ["Bonus", score.bonus, "보너스"],
            ].map(([k, v, desc]) => (
              <div key={k} className="text-center p-3 bg-card/50 rounded-lg border border-border/50">
                <div className="text-xs text-text-secondary mb-1">{k}</div>
                <div className={`font-bold text-lg font-mono ${
                  v > 0 ? "profit-text" : v < 0 ? "loss-text" : "text-text-secondary"
                }`}>{v ?? 0}</div>
                <div className="text-xs text-text-muted mt-1">{desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Position & News */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Position Card */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Wallet className="w-4 h-4" /> 포지션 정보
            </h3>
          </div>
          {position ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-text-secondary mb-1">진입가</div>
                  <div className="font-mono font-medium">₩{fmt(position.entry_price)}</div>
                </div>
                <div>
                  <div className="text-text-secondary mb-1">수량</div>
                  <div className="font-mono font-medium">{position.quantity} BTC</div>
                </div>
                <div>
                  <div className="text-text-secondary mb-1">투입금</div>
                  <div className="font-mono font-medium">₩{fmt(position.entry_krw)}</div>
                </div>
                {position?.pnl_pct != null && (
                  <div>
                    <div className="text-text-secondary mb-1">수익률</div>
                    <div className={`font-mono font-medium ${
                      position.pnl_pct >= 0 ? "profit-text" : "loss-text"
                    }`}>
                      {pct(position.pnl_pct)}
                    </div>
                  </div>
                )}
              </div>
              <div className="pt-3 border-t border-border text-xs text-text-secondary">
                <div className="flex justify-between">
                  <span>총평가</span>
                  <span className="font-mono">₩{fmt(summary.total_eval)}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span>미실현 손익</span>
                  <span className={`font-mono ${
                    summary.unrealized_pnl >= 0 ? "profit-text" : "loss-text"
                  }`}>
                    ₩{fmt(summary.unrealized_pnl)}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-text-secondary">포지션 없음 (대기 중)</div>
          )}
        </div>

        {/* News Card */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Newspaper className="w-4 h-4" /> 뉴스 감성
            </h3>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {newsRows.length > 0 ? (
              newsRows.slice(0, 8).map((row, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-text-muted mt-0.5">•</span>
                  <span className="text-text-secondary leading-relaxed">{row.headline || row.title}</span>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-text-secondary text-sm">뉴스 데이터 없음</div>
            )}
          </div>
        </div>
      </div>

      {/* TradingView + System Status — 묶음 (간격 축소) */}
      <div className="space-y-3">
        <div className="card p-0 overflow-hidden">
          <div className="px-4 pt-4 pb-2 border-b border-border">
            <h3 className="text-sm font-medium text-text-primary">실시간 차트 (UPBIT:BTCKRW)</h3>
            <p className="text-xs text-text-secondary mt-0.5">인디케이터·드로잉 도구 포함 — TradingView 제공</p>
          </div>
          <TvWidget widgetType="advanced-chart" config={TV_BTC_CONFIG} height={500} />
        </div>

        {sys && (
          <div className="card">
            <div className="card-header">
              <h3 className="text-sm font-medium text-text-primary">시스템 상태</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="CPU"
                value={`${sys.cpu ?? 0}%`}
                size="compact"
                tooltip="시스템 CPU 사용률"
              />
              <StatCard
                label="메모리"
                value={`${sys.mem_pct ?? 0}%`}
                size="compact"
                tooltip="시스템 메모리 사용률"
              />
              <StatCard
                label="디스크"
                value={`${sys.disk_pct ?? 0}%`}
                size="compact"
                tooltip="디스크 사용률"
              />
              <StatCard
                label="업비트 연동"
                value={sys.upbit_ok ? "정상" : "오류"}
                trend={sys.upbit_ok ? "up" : "down"}
                size="compact"
                tooltip="거래소 API 연결 상태"
              />
            </div>
          </div>
        )}
      </div>

      {/* Recent Trades */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-text-primary">최근 거래 기록</h3>
        </div>
        <TradeTable trades={trades || []} columns={TRADE_COLS} />
      </div>
    </div>
  );
}
