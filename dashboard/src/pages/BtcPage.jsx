import { Newspaper, RefreshCw, ShieldCheck, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import {
  getBtcCandles,
  getBtcComposite,
  getBtcDecisionLog,
  getBtcFilters,
  getBtcNews,
  getBtcTrades,
} from "../api";
import usePolling from "../hooks/usePolling";
import { usePortfolio } from "../context/PortfolioContext";
import { compactTime, krw, marketTone, num, pct } from "../lib/format";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import MetricRow, { getSignalColor } from "../components/ui/MetricRow";
import { EmptyState, ErrorState } from "../components/ui/PageState";
import ScoreRadial from "../components/ui/ScoreRadial";
import ValuePair from "../components/ui/ValuePair";
import { BtcStrategyPanel } from "../components/StrategyPanel";

function normalizeFunding(value) {
  const numeric = Number(value || 0);
  if (Math.abs(numeric) <= 1) {
    return numeric * 100;
  }
  return numeric;
}

function scoreBars(comp, filters) {
  const raw = [
    { label: "F&G", value: Number(comp?.fg_value || 0) },
    { label: "RSI", value: Number(comp?.rsi_d || 0) },
    { label: "Trend", value: Number(comp?.trend_score ?? comp?.trend_strength ?? 0) },
    { label: "BB", value: Number(comp?.bb_score ?? 0) },
    { label: "Volume", value: Number(comp?.volume_score ?? 0) },
    { label: "Funding", value: normalizeFunding(filters?.funding_rate ?? comp?.funding_score ?? 0) },
  ];

  return raw.map((signal) => ({
    ...signal,
    progress: Math.max(0, Math.min(100, Number(signal.value || 0))),
    color: getSignalColor(Number(signal.value || 0)),
  }));
}

function newsVariant(sentiment) {
  const key = String(sentiment || "neutral").toLowerCase();
  if (key.includes("bull")) return "bullish";
  if (key.includes("bear")) return "bearish";
  return "neutral";
}

function normalizeAction(action) {
  return String(action || "HOLD").toUpperCase();
}

function actionVariant(action) {
  const normalized = normalizeAction(action);
  if (normalized === "BUY") return "buy";
  if (normalized === "SELL") return "sell";
  return "hold";
}

function positionDelta(summary, currentPosition) {
  if (currentPosition?.pnl_pct != null) {
    return Number(currentPosition.pnl_pct);
  }
  if (summary?.unrealized_pnl_pct != null) {
    return Number(summary.unrealized_pnl_pct);
  }
  return 0;
}

function tradePnl(trade) {
  if (trade?.pnl_pct != null) {
    return Number(trade.pnl_pct);
  }
  if (trade?.return_pct != null) {
    return Number(trade.return_pct);
  }
  return 0;
}

function scoreLabel(score) {
  if (score <= 30) return "리스크 오프";
  if (score <= 70) return "중립";
  return "리스크 온";
}

function CompactSignalRow({ label, value, color }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}66` }}
        />
        <span className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-secondary)]">
          {label}
        </span>
      </div>
      <span className="numeric text-sm text-[color:var(--text-primary)]">{Number(value || 0).toFixed(0)}</span>
    </div>
  );
}

function DecisionPlaceholder() {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3 text-sm text-[color:var(--text-muted)]">
      <span className="h-2 w-2 animate-pulse rounded-full bg-white/30" />
      <span>다음 결정 대기 중...</span>
    </div>
  );
}

function BtcAccountBanner({ summary, loading }) {
  if (loading) return <LoadingSkeleton height={80} />;
  if (!summary || !summary.estimated_asset) return null;

  const krwBalance = Number(summary.krw_balance || 0);
  const totalEval = Number(summary.total_eval || 0);
  const estimatedAsset = Number(summary.estimated_asset || 0);
  const unrealizedPnl = Number(summary.unrealized_pnl || 0);
  const unrealizedPct = Number(summary.unrealized_pnl_pct || 0);
  const realizedPnl = Number(summary.realized_pnl || 0);
  const winrate = Number(summary.winrate || 0);
  const wins = Number(summary.wins || 0);
  const losses = Number(summary.losses || 0);

  const cells = [
    { label: "KRW 잔고", value: krw(krwBalance), delta: null },
    { label: "BTC 평가금액", value: krw(totalEval), delta: null },
    { label: "총 자산", value: krw(estimatedAsset), delta: null },
    { label: "미실현 손익", value: krw(unrealizedPnl), delta: unrealizedPct, emphasize: true },
    { label: "실현 손익 / 승률", value: `${krw(realizedPnl)} / ${winrate.toFixed(1)}%`, delta: null, sub: `${wins}승 ${losses}패` },
  ];

  return (
    <div className="rounded-[var(--panel-radius)] border border-white/10 bg-[color:var(--bg-panel)] px-4 py-3 shadow-[var(--shadow-panel)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
          BTC 계좌 현황 (Upbit)
        </span>
        <Badge variant={unrealizedPct >= 0 ? "profit" : "loss"}>
          {unrealizedPct >= 0 ? "+" : ""}{Number(unrealizedPct).toFixed(2)}%
        </Badge>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {cells.map((cell) => (
          <div key={cell.label} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">{cell.label}</div>
            <div
              className={`mt-1 numeric text-sm font-semibold ${
                cell.delta != null
                  ? cell.delta >= 0
                    ? "text-[color:var(--color-profit)]"
                    : "text-[color:var(--color-loss)]"
                  : "text-[color:var(--text-primary)]"
              }`}
            >
              {cell.value}
            </div>
            {cell.delta != null && (
              <div className={`mt-0.5 numeric text-[11px] ${cell.delta >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                {pct(cell.delta)}
              </div>
            )}
            {cell.sub && (
              <div className="mt-0.5 text-[11px] text-[color:var(--text-muted)]">{cell.sub}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const TIMEFRAMES = [
  { label: "5분",  interval: "minute5",  count: 120, pollMs: 30000  },
  { label: "10분", interval: "minute10", count: 144, pollMs: 60000  },
  { label: "1시간", interval: "minute60", count: 168, pollMs: 60000  },
  { label: "주봉",  interval: "week",     count: 52,  pollMs: 300000 },
  { label: "월봉",  interval: "month",    count: 48,  pollMs: 300000 },
  { label: "연봉",  interval: "day",      count: 365, pollMs: 300000 },
];

export default function BtcPage() {
  const [tfIndex, setTfIndex] = useState(0);
  const tf = TIMEFRAMES[tfIndex];

  const { data: composite, error: compositeError, loading: compositeLoading } = usePolling(getBtcComposite, 30000);
  const { btcPortfolio: portfolio } = usePortfolio();
  const portfolioLoading = portfolio === null;
  const { data: trades } = usePolling(getBtcTrades, 60000);
  const { data: decisionLog } = usePolling(() => getBtcDecisionLog(8), 30000);
  const { data: candles, loading: candlesLoading } = usePolling(
    () => getBtcCandles(tf.interval, tf.count),
    tf.pollMs,
    [tf.interval],
  );
  const { data: news } = usePolling(getBtcNews, 120000);
  const { data: filters } = usePolling(getBtcFilters, 30000);

  const candleSeries = useMemo(() => {
    const rows = Array.isArray(candles?.candles) ? candles.candles : Array.isArray(candles) ? candles : [];
    return rows.map((row) => ({
      time: row?.time || row?.timestamp,
      open: Number(row?.open ?? row?.opening_price ?? row?.trade_price ?? 0),
      high: Number(row?.high ?? row?.high_price ?? row?.trade_price ?? 0),
      low: Number(row?.low ?? row?.low_price ?? row?.trade_price ?? 0),
      close: Number(row?.close ?? row?.trade_price ?? 0),
      volume: Number(row?.volume ?? row?.candle_acc_trade_volume ?? 0),
      value: Number(row?.close ?? row?.trade_price ?? 0),
    }));
  }, [candles]);

  const currentPosition = portfolio?.open_positions?.[0];
  const summary = portfolio?.summary || {};
  const lastPrice = Number(summary?.btc_price || summary?.current_price || candleSeries.at(-1)?.close || 0);
  const score = Number(
    composite?.composite_score ??
      composite?.score ??
      composite?.final_score ??
      composite?.signal_score ??
      0,
  );
  const signals = scoreBars(composite, filters);
  const portfolioDelta = positionDelta(summary, currentPosition);
  const tradeRows = trades?.trades || trades || [];
  const newsRows = news?.items || news || [];
  const decisionRows = decisionLog?.decisions || [];
  const watchlist = [
    { symbol: "BTC", label: "BTCKRW", value: krw(lastPrice), delta: portfolioDelta, tag: "Live" },
  ];

  const leftRail = (
    <>
      <Card title="시세" delay={0}>
        <div className="space-y-2">
          {watchlist.map((item) => (
            <div
              key={item.symbol}
              className="flex w-full items-center justify-between rounded-xl border border-white/15 bg-white/[0.05] px-3 py-3 text-left"
            >
              <div>
                <div className="text-sm font-semibold text-[color:var(--text-primary)]">{item.symbol}</div>
                <div className="mt-1 text-xs text-[color:var(--text-muted)]">{item.label}</div>
              </div>
              <div className="text-right">
                <div className="numeric text-sm text-[color:var(--text-primary)]">{item.value}</div>
                <div className={`mt-1 numeric text-xs ${Number(item.delta || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                  {pct(item.delta || 0)}
                </div>
                <div className="mt-1 text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">{item.tag}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="신호 지표" delay={1}>
        <div className="space-y-4">
          {signals.map((signal) => (
            <MetricRow
              key={signal.label}
              label={signal.label}
              value={signal.value.toFixed(0)}
              progress={signal.progress}
              tone={signal.color}
            />
          ))}
        </div>
      </Card>

      <Card title="시장 필터" icon={<ShieldCheck size={14} />} delay={2}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">펀딩비</div>
              <div className={`mt-1 numeric text-sm ${Number(filters?.funding_rate || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                {Number(filters?.funding_rate || 0).toFixed(4)}%
              </div>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">롱/숏 비율</div>
              <div className="mt-1 numeric text-sm text-[color:var(--text-primary)]">
                {Number(filters?.long_short_ratio || 0).toFixed(2)}x
              </div>
            </div>
          </div>

          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
              실행 기록
            </div>
            <div className="space-y-2">
              {decisionRows.slice(0, 4).map((row, index) => (
                <div key={row.created_at || index} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <Badge variant={actionVariant(row.action)}>{normalizeAction(row.action)}</Badge>
                    <span className="numeric text-xs text-[color:var(--text-muted)]">{compactTime(row.created_at || row.timestamp)}</span>
                  </div>
                  <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                    {row.reason || row.reasoning || "판단 근거 없음"}
                  </div>
                </div>
              ))}
              {decisionRows.length === 0 ? <DecisionPlaceholder /> : null}
            </div>
          </div>
        </div>
      </Card>
    </>
  );

  if (compositeError) {
    return <ErrorState message={`BTC API 연결 실패: ${compositeError}`} />;
  }

  return (
    <div className="space-y-[var(--content-gap)]">
      <BtcAccountBanner summary={summary} loading={portfolioLoading} />
      <div className="grid gap-[var(--content-gap)] xl:grid-cols-[240px_minmax(0,1fr)_320px] lg:grid-cols-[minmax(0,1fr)_320px]">
        <aside className="hidden space-y-[var(--content-gap)] xl:block">{leftRail}</aside>

        <div className="space-y-[var(--content-gap)]">
          <div className="grid gap-[var(--content-gap)] md:grid-cols-2 xl:hidden">{leftRail}</div>

          <Card
            accent
            title="BTC 현황"
            delay={2}
            bodyClassName="space-y-4"
            action={
              <div className="flex gap-0.5">
                {TIMEFRAMES.map((t, i) => (
                  <button
                    key={t.label}
                    type="button"
                    onClick={() => setTfIndex(i)}
                    className={`rounded-full px-2 py-1 text-[11px] transition-colors ${
                      tfIndex === i
                        ? "bg-white/10 text-white font-medium"
                        : "text-[color:var(--text-secondary)] hover:text-white"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            }
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-[color:var(--text-muted)]">BTCKRW</div>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <span className="numeric text-3xl font-bold text-[color:var(--text-primary)] lg:text-4xl">
                    {krw(lastPrice)}
                  </span>
                  <Badge variant={marketTone(portfolioDelta)}>{pct(portfolioDelta)}</Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="btc">업비트</Badge>
                  <Badge variant="neutral">현물</Badge>
                  <Badge variant="neutral">5분봉</Badge>
                  <Badge variant="info">실시간</Badge>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">총 자산</div>
                  <div className="mt-1 numeric text-sm text-[color:var(--text-primary)]">{krw(summary?.estimated_asset || 0)}</div>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">원화 잔고</div>
                  <div className="mt-1 numeric text-sm text-[color:var(--text-primary)]">{krw(summary?.krw_balance || 0)}</div>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">레짐</div>
                  <div className="mt-1 text-sm text-[color:var(--text-primary)]">{composite?.regime || composite?.trend || "전환"}</div>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">종합 점수</div>
                  <div className="mt-1 numeric text-sm text-[color:var(--text-primary)]">{score.toFixed(0)}</div>
                </div>
              </div>
            </div>

            {candlesLoading ? (
              <LoadingSkeleton height={460} />
            ) : (
              <LightweightPriceChart title={`가격 / 거래량 (${tf.label})`} data={candleSeries} height={460} />
            )}
          </Card>

          <div className="grid gap-[var(--content-gap)] xl:grid-cols-2">
            <Card title="최근 거래" delay={3} bodyClassName="p-0">
              <div className="overflow-x-auto scrollbar-subtle px-4 pb-4">
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>시각</th>
                      <th>액션</th>
                      <th>가격</th>
                      <th>손익</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tradeRows.slice(0, 8).map((trade, index) => {
                      const action = normalizeAction(trade.action || trade.trade_type || "HOLD");
                      const pnl = tradePnl(trade);
                      return (
                        <tr key={trade.id || index}>
                          <td className="numeric text-[color:var(--text-secondary)]">{compactTime(trade.created_at || trade.timestamp)}</td>
                          <td>
                            <Badge variant={actionVariant(action)}>{action}</Badge>
                          </td>
                          <td className="numeric">{krw(trade.price || trade.entry_price)}</td>
                          <td className={`numeric ${pnl >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                            {pct(pnl)}
                          </td>
                        </tr>
                      );
                    })}
                    {tradeRows.length === 0 ? (
                      <tr>
                        <td colSpan="4">
                          <EmptyState message="최근 BTC 거래 내역이 없습니다." />
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card title="뉴스" icon={<Newspaper size={14} />} delay={4}>
              <div className="space-y-3">
                {newsRows.slice(0, 6).map((item, index) => (
                  <article
                    key={item.id || item.url || index}
                    className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="line-clamp-2 text-sm font-medium text-[color:var(--text-primary)]">
                          {item.title || item.headline || "제목 없음"}
                        </div>
                        <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                          {item.source || "출처 불명"}
                        </div>
                      </div>
                      <Badge variant={newsVariant(item.sentiment)}>{item.sentiment || "Neutral"}</Badge>
                    </div>
                  </article>
                ))}
                {newsRows.length === 0 ? <EmptyState message="BTC 뉴스가 없습니다." /> : null}
              </div>
            </Card>
          </div>
        </div>

        <aside className="space-y-[var(--content-gap)]">
          <Card title="종합 점수" icon={<TrendingUp size={14} />} delay={5}>
            {compositeLoading ? (
              <LoadingSkeleton height={300} />
            ) : (
              <>
                <ScoreRadial score={score} />
                <div className="mt-3 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2 text-center">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">매매 신호</div>
                  <div className="mt-1 text-sm text-[color:var(--text-primary)]">{scoreLabel(score)}</div>
                </div>
                <div className="mt-4 space-y-2">
                  {signals.map((signal) => (
                    <CompactSignalRow
                      key={signal.label}
                      label={signal.label}
                      value={signal.value}
                      color={signal.color}
                    />
                  ))}
                </div>
              </>
            )}
          </Card>

          <Card
            title="현재 포지션"
            icon={<RefreshCw size={14} />}
            action={<Badge variant={currentPosition ? "profit" : "neutral"}>{currentPosition ? "보유중" : "미보유"}</Badge>}
            delay={6}
          >
            {portfolioLoading ? (
              <LoadingSkeleton height={220} />
            ) : (
              <div className="divide-y divide-white/5">
                <ValuePair label="진입가" value={krw(currentPosition?.entry_price || currentPosition?.avg_price || 0)} />
                <ValuePair label="현재가" value={krw(lastPrice)} />
                <ValuePair
                  label="손익률"
                  value={pct(portfolioDelta)}
                  tone={marketTone(portfolioDelta)}
                  emphasize
                />
                <ValuePair label="수량" value={num(currentPosition?.quantity || currentPosition?.size || 0, 6)} />
                <ValuePair label="원화 잔고" value={krw(summary?.krw_balance || 0)} />
              </div>
            )}
          </Card>

          <BtcStrategyPanel composite={composite} filters={filters} decisions={decisionRows} loading={compositeLoading} />
        </aside>
      </div>
    </div>
  );
}
