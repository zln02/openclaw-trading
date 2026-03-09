import {
  Bitcoin,
  Gauge,
  Wallet,
  Clock,
  Newspaper,
  TrendingUp,
  TrendingDown,
  Minus,
  Shield,
  Activity,
  AlertTriangle,
} from "lucide-react";
import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import ScoreGauge from "../components/ScoreGauge";
import StatCard from "../components/StatCard";
import TvWidget from "../components/TvWidget";
import usePolling from "../hooks/usePolling";

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
  getBtcFilters,
} from "../api";

const fmt = (n) => (n != null ? Number(n).toLocaleString() : "—");
const pct = (n) => (n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—");

const fetchBtcRtPrice = () => getBtcRealtimePrice("KRW-BTC", "btc");
const fetchBtcOrderbook = () => getBtcRealtimeOrderbook("upbit", "KRW-BTC");
const fetchBtcAlt = () => getBtcRealtimeAlt("BTC");
const fetchBtcNews = () => getBtcRealtimeNews("BTC", 10);

export default function BtcPage() {
  const { data: comp, error: compError } = usePolling(getBtcComposite, 30000);
  const { data: port } = usePolling(getBtcPortfolio, 30000);
  const { data: trades } = usePolling(getBtcTrades, 60000);
  const { data: news } = usePolling(fetchBtcNews, 120000);
  const { data: sys } = usePolling(getBtcSystem, 60000);
  const { data: rtPrice } = usePolling(fetchBtcRtPrice, 5000);
  const { data: orderbook } = usePolling(fetchBtcOrderbook, 5000);
  const { data: alt } = usePolling(fetchBtcAlt, 60000);
  const { data: filters } = usePolling(getBtcFilters, 60000);

  const score = comp?.composite;
  const summary = useMemo(() => port?.summary || {}, [port?.summary]);
  const openPositions = port?.open_positions || [];
  const firstPos = openPositions[0] || null;
  const priceNow = rtPrice?.price;
  const newsRows = Array.isArray(news?.items) ? news.items : [];

  // 수익 곡선: closed_positions pnl_pct 누적
  const pnlCurve = useMemo(() => {
    const closed = (port?.closed_positions || [])
      .filter((p) => p.pnl_pct != null)
      .toSorted((a, b) => (a.exit_time || "").localeCompare(b.exit_time || ""));
    let cumulative = 0;
    return closed.map((p) => {
      cumulative += Number(p.pnl_pct || 0);
      return { date: (p.exit_time || "").slice(5, 10), cum: Math.round(cumulative * 100) / 100 };
    });
  }, [port?.closed_positions]);

  // 거래 통계
  const tradeStats = useMemo(() => {
    const closed = port?.closed_positions || [];
    const wins = closed.filter((p) => (p.pnl_pct || 0) > 0);
    const losses = closed.filter((p) => (p.pnl_pct || 0) < 0);
    const avgWin = wins.length ? wins.reduce((s, p) => s + p.pnl_pct, 0) / wins.length : 0;
    const avgLoss = losses.length ? losses.reduce((s, p) => s + p.pnl_pct, 0) / losses.length : 0;
    const profitFactor = avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0;
    let maxConsec = 0;
    let cur = 0;
    closed
      .toSorted((a, b) => (a.exit_time || "").localeCompare(b.exit_time || ""))
      .forEach((p) => {
        if ((p.pnl_pct || 0) < 0) {
          cur++;
          maxConsec = Math.max(maxConsec, cur);
        } else {
          cur = 0;
        }
      });
    return {
      total: closed.length,
      winrate: summary.winrate ?? 0,
      avgWin: avgWin.toFixed(2),
      avgLoss: avgLoss.toFixed(2),
      profitFactor: profitFactor.toFixed(2),
      maxConsec,
    };
  }, [port?.closed_positions, summary]);

  // 에이전트 다음 액션
  const nextAction = useMemo(() => {
    if (firstPos) {
      const sl = firstPos.stop_loss ?? firstPos.entry_price * 0.97;
      const tp = firstPos.take_profit ?? firstPos.entry_price * 1.12;
      return { type: "holding", sl, tp };
    }
    const s = score?.total ?? 0;
    const threshold = comp?.buy_threshold ?? 45;
    if (s >= threshold) {
      return { type: "signal", score: s, threshold };
    }
    return { type: "waiting", score: s, threshold };
  }, [firstPos, score, comp]);

  return (
    <div className="space-y-6">
      {/* API Error Banner */}
      {compError && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          BTC 데이터 로드 실패: {compError}
        </div>
      )}

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
          sub={
            comp?.fg_value != null
              ? comp.fg_value < 30
                ? "극공포"
                : comp.fg_value > 70
                  ? "탐욕"
                  : "중립"
              : null
          }
          trend={comp?.fg_value < 40 ? "down" : comp?.fg_value > 60 ? "up" : null}
          icon={Gauge}
          tooltip="시장 심리 지수 (0-100)"
        />
        {/* 1시간 추세 — 방향 화살표 */}
        {(() => {
          const t = String(comp?.trend ?? "");
          const isUp = t.includes("UP") && !t.includes("DOWN");
          const isDown = t.includes("DOWN");
          const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;
          const color = isUp ? "text-profit" : isDown ? "text-loss" : "text-text-secondary";
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
          <div
            className={`data-value text-xl mb-3 ${
              comp?.rsi_d < 30
                ? "text-profit"
                : comp?.rsi_d > 70
                  ? "text-loss"
                  : "text-text-primary"
            }`}
          >
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
                <span>과매도</span>
                <span>중립</span>
                <span>과매수</span>
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
              <div
                key={k}
                className="text-center p-3 bg-card/50 rounded-lg border border-border/50"
              >
                <div className="text-xs text-text-secondary mb-1">{k}</div>
                <div
                  className={`font-bold text-lg font-mono ${
                    v > 0 ? "profit-text" : v < 0 ? "loss-text" : "text-text-secondary"
                  }`}
                >
                  {v ?? 0}
                </div>
                <div className="text-xs text-text-muted mt-1">{desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* [A] 매매 필터 상태 */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Shield className="w-4 h-4" /> 매매 필터 상태
          </h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {/* 김치 프리미엄 */}
          {(() => {
            const v = filters?.kimchi_premium;
            const blocked = filters?.kimchi_blocked;
            const color = blocked ? "text-loss" : v > 3 ? "text-amber-400" : "text-profit";
            const badge = blocked
              ? "bg-loss/10 border-loss/30"
              : v > 3
                ? "bg-amber-400/10 border-amber-400/30"
                : "bg-profit/10 border-profit/30";
            return (
              <div className={`p-3 rounded-lg border ${badge}`}>
                <div className="text-xs text-text-secondary mb-1">김치 프리미엄</div>
                <div className={`font-mono font-bold text-lg ${color}`}>
                  {v != null ? `${v}%` : "—"}
                </div>
                <div className={`text-xs mt-1 ${color}`}>
                  {blocked ? "차단" : v > 3 ? "주의" : "정상"}
                </div>
              </div>
            );
          })()}
          {/* 펀딩비 */}
          {(() => {
            const v = filters?.funding_rate;
            const overheated = filters?.funding_overheated;
            const sig = filters?.funding_signal || "NEUTRAL";
            const warn = !overheated && (sig.includes("LONG") || sig.includes("SHORT"));
            const color = overheated ? "text-loss" : warn ? "text-amber-400" : "text-profit";
            const badge = overheated
              ? "bg-loss/10 border-loss/30"
              : warn
                ? "bg-amber-400/10 border-amber-400/30"
                : "bg-profit/10 border-profit/30";
            return (
              <div className={`p-3 rounded-lg border ${badge}`}>
                <div className="text-xs text-text-secondary mb-1">펀딩비</div>
                <div className={`font-mono font-bold text-lg ${color}`}>
                  {v != null ? `${v}%` : "—"}
                </div>
                <div className={`text-xs mt-1 ${color}`}>{sig}</div>
              </div>
            );
          })()}
          {/* 일일 횟수 */}
          {(() => {
            const cur = filters?.today_trades ?? 0;
            const max = filters?.max_trades_per_day ?? 3;
            const full = cur >= max;
            const near = cur >= max - 1;
            const color = full ? "text-loss" : near ? "text-amber-400" : "text-profit";
            const badge = full
              ? "bg-loss/10 border-loss/30"
              : near
                ? "bg-amber-400/10 border-amber-400/30"
                : "bg-profit/10 border-profit/30";
            return (
              <div className={`p-3 rounded-lg border ${badge}`}>
                <div className="text-xs text-text-secondary mb-1">오늘 매매 횟수</div>
                <div className={`font-mono font-bold text-lg ${color}`}>
                  {cur} / {max}
                </div>
                <div className={`text-xs mt-1 ${color}`}>
                  {full ? "한도 도달" : near ? "주의" : "정상"}
                </div>
              </div>
            );
          })()}
          {/* 낙폭 */}
          {(() => {
            const pnl = filters?.today_pnl_pct ?? 0;
            const maxLoss = filters?.max_daily_loss ?? -8.0;
            const danger = pnl <= maxLoss + 3;
            const warn = !danger && pnl <= maxLoss + 5;
            const color = danger ? "text-loss" : warn ? "text-amber-400" : "text-profit";
            const badge = danger
              ? "bg-loss/10 border-loss/30"
              : warn
                ? "bg-amber-400/10 border-amber-400/30"
                : "bg-profit/10 border-profit/30";
            return (
              <div className={`p-3 rounded-lg border ${badge}`}>
                <div className="text-xs text-text-secondary mb-1">오늘 손익</div>
                <div className={`font-mono font-bold text-lg ${color}`}>{pct(pnl)}</div>
                <div className="text-xs mt-1 text-text-muted">한도 {maxLoss}%</div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* ── Open Positions Table ── */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Wallet className="w-4 h-4" /> 오픈 포지션
            {openPositions.length > 0 && (
              <span className="ml-1 text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">
                {openPositions.length}개
              </span>
            )}
          </h3>
          {nextAction &&
            (() => {
              const isHolding = nextAction.type === "holding";
              const isSignal = nextAction.type === "signal";
              const labelColor = isHolding
                ? "text-blue-400"
                : isSignal
                  ? "text-profit"
                  : "text-text-secondary";
              const label = isHolding ? "보유 중" : isSignal ? "매수 신호" : "대기 중";
              return (
                <div className={`flex items-center gap-1.5 text-xs font-medium ${labelColor}`}>
                  <Activity className="w-3 h-3" />
                  {label}
                  {isHolding && (
                    <span className="text-text-muted font-mono font-normal ml-1">
                      SL ₩{fmt(Math.round(nextAction.sl))} / TP ₩{fmt(Math.round(nextAction.tp))}
                    </span>
                  )}
                  {!isHolding && (
                    <span className="text-text-muted font-normal ml-1">
                      스코어 {nextAction.score} / 기준 {nextAction.threshold}
                    </span>
                  )}
                </div>
              );
            })()}
        </div>
        {/* 잔고 요약 — 항상 표시 */}
        <div className="px-4 py-3 border-b border-border flex flex-wrap gap-6 text-xs text-text-secondary bg-card/30">
          <div>
            원화 잔고{" "}
            <span className="font-mono text-text-primary ml-1">₩{fmt(summary.krw_balance)}</span>
          </div>
          <div>
            총 추정자산{" "}
            <span className="font-mono text-amber-400 font-semibold ml-1">
              ₩{fmt(summary.estimated_asset)}
            </span>
          </div>
          {openPositions.length > 0 && (
            <>
              <div>
                총 투입금{" "}
                <span className="font-mono text-text-primary ml-1">
                  ₩{fmt(summary.total_invested)}
                </span>
              </div>
              <div>
                미실현 손익{" "}
                <span
                  className={`font-mono ml-1 ${(summary.unrealized_pnl ?? 0) >= 0 ? "profit-text" : "loss-text"}`}
                >
                  ₩{fmt(summary.unrealized_pnl)}
                  {summary.unrealized_pnl_pct != null && (
                    <span className="ml-1 opacity-75">({pct(summary.unrealized_pnl_pct)})</span>
                  )}
                </span>
              </div>
            </>
          )}
          <div>
            실현 손익{" "}
            <span
              className={`font-mono ml-1 ${(summary.realized_pnl ?? 0) >= 0 ? "profit-text" : "loss-text"}`}
            >
              ₩{fmt(summary.realized_pnl)}
            </span>
          </div>
        </div>
        {openPositions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["진입시간", "진입가", "수량 (BTC)", "투입금", "현재가", "수익률"].map((h) => (
                    <th
                      key={h}
                      className={`py-3 px-3 text-xs text-text-secondary font-medium uppercase tracking-wide ${
                        h === "진입시간" ? "text-left" : "text-right"
                      }`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {openPositions.map((pos) => (
                  <tr
                    key={pos.id}
                    className="border-b border-border/50 hover:bg-card/30 transition-colors"
                  >
                    <td className="py-3 px-3 text-xs text-text-secondary">
                      {pos.entry_time?.slice(5, 16) || "—"}
                    </td>
                    <td className="text-right py-3 px-3 font-mono">₩{fmt(pos.entry_price)}</td>
                    <td className="text-right py-3 px-3 font-mono">{pos.quantity}</td>
                    <td className="text-right py-3 px-3 font-mono">₩{fmt(pos.entry_krw)}</td>
                    <td className="text-right py-3 px-3 font-mono">
                      ₩{fmt(pos.current_price_krw)}
                    </td>
                    <td
                      className={`text-right py-3 px-3 font-mono font-semibold ${
                        (pos.pnl_pct ?? 0) >= 0 ? "profit-text" : "loss-text"
                      }`}
                    >
                      {pct(pos.pnl_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-text-secondary">포지션 없음 (대기 중)</div>
        )}
      </div>

      {/* ── 거래 로그 | 뉴스 ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trade Log */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Activity className="w-4 h-4" /> 거래 로그
            </h3>
          </div>
          <div className="space-y-0 max-h-52 overflow-y-auto">
            {(trades || []).length > 0 ? (
              trades.slice(0, 20).map((t, i) => {
                const isBuy = String(t.action || "").toUpperCase() === "BUY";
                const isSell = String(t.action || "").toUpperCase() === "SELL";
                return (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-xs py-1.5 border-b border-border/30 last:border-0"
                  >
                    <span className="text-text-muted shrink-0 w-[70px]">
                      {(t.timestamp || "").slice(5, 16)}
                    </span>
                    <span
                      className={`shrink-0 font-semibold w-7 ${isBuy ? "profit-text" : isSell ? "loss-text" : "text-text-secondary"}`}
                    >
                      {isBuy ? "매수" : isSell ? "매도" : "—"}
                    </span>
                    <span className="font-mono text-text-primary shrink-0">₩{fmt(t.price)}</span>
                    <span className="text-text-muted truncate flex-1 pl-1">{t.reason || "—"}</span>
                    {t.pnl_pct != null && (
                      <span
                        className={`font-mono shrink-0 ${t.pnl_pct > 0 ? "profit-text" : t.pnl_pct < 0 ? "loss-text" : "text-text-secondary"}`}
                      >
                        {pct(t.pnl_pct)}
                      </span>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="text-center py-6 text-text-secondary text-sm">거래 로그 없음</div>
            )}
          </div>
        </div>

        {/* News with links */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Newspaper className="w-4 h-4" /> 뉴스 감성
            </h3>
          </div>
          <div className="space-y-2 max-h-52 overflow-y-auto">
            {newsRows.length > 0 ? (
              newsRows.slice(0, 8).map((row, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-text-muted mt-0.5 shrink-0">•</span>
                  {row.url ? (
                    <a
                      href={row.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 leading-relaxed transition-colors"
                    >
                      {row.headline || row.title}
                    </a>
                  ) : (
                    <span className="text-text-secondary leading-relaxed">
                      {row.headline || row.title}
                    </span>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-6 text-text-secondary text-sm">뉴스 데이터 없음</div>
            )}
          </div>
        </div>
      </div>

      {/* [C] 누적 수익 곡선 */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> 누적 수익 곡선
          </h3>
        </div>
        {pnlCurve.length > 1 ? (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={pnlCurve}>
              <XAxis dataKey="date" stroke="#6b6d7a" tick={{ fontSize: 11 }} />
              <YAxis stroke="#6b6d7a" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                formatter={(v) => [`${String(v)}%`, "누적 수익률"]}
                contentStyle={{
                  background: "#1a1c26",
                  border: "1px solid #2a2d3a",
                  borderRadius: "8px",
                  fontSize: 12,
                }}
              />
              <ReferenceLine y={0} stroke="#2a2d3a" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="cum" stroke="#00c087" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center py-12">
            <div className="text-text-secondary text-sm">체결 이력 축적 중</div>
            <div className="text-text-muted text-xs mt-1">
              CLOSED 포지션 2건 이상 시 곡선 표시 — 현재 {port?.closed_positions?.length ?? 0}건
            </div>
          </div>
        )}
      </div>

      {/* TradingView + System Status — 묶음 (간격 축소) */}
      <div className="space-y-3">
        <div className="card p-0 overflow-hidden">
          <div className="px-4 pt-4 pb-2 border-b border-border">
            <h3 className="text-sm font-medium text-text-primary">실시간 차트 (UPBIT:BTCKRW)</h3>
            <p className="text-xs text-text-secondary mt-0.5">
              인디케이터·드로잉 도구 포함 — TradingView 제공
            </p>
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

      {/* [D] 거래 통계 */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Activity className="w-4 h-4" /> 거래 통계
          </h3>
        </div>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
          {[
            { label: "총 거래", value: tradeStats.total },
            { label: "승률", value: `${tradeStats.winrate}%` },
            { label: "평균 수익", value: `${tradeStats.avgWin}%`, pos: true },
            { label: "평균 손실", value: `${tradeStats.avgLoss}%`, neg: true },
            { label: "손익비", value: tradeStats.profitFactor },
            {
              label: "최대연속손실",
              value: `${tradeStats.maxConsec}회`,
              neg: tradeStats.maxConsec > 2,
            },
          ].map(({ label, value, pos, neg }) => (
            <div
              key={label}
              className="text-center p-3 bg-card/50 rounded-lg border border-border/50"
            >
              <div className="text-xs text-text-secondary mb-1">{label}</div>
              <div
                className={`font-bold text-base font-mono ${pos ? "text-profit" : neg ? "text-loss" : "text-text-primary"}`}
              >
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
