import {
  Bitcoin,
  CandlestickChart,
  Newspaper,
  Radar,
  ShieldCheck,
  Activity,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  getBtcCandles,
  getBtcComposite,
  getBtcFilters,
  getBtcLiveActivity,
  getBtcNews,
  getBtcPortfolio,
  getBtcTrades,
} from "../api";
import usePolling from "../hooks/usePolling";
import { useLang } from "../hooks/useLang";
import { compactTime, krw, pct, sparkline } from "../lib/format";
import CircularGauge from "../components/ui/CircularGauge";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
import { ErrorState, EmptyState } from "../components/ui/PageState";
import ErrorBoundary from "../components/ui/ErrorBoundary";
import StatCard from "../components/ui/StatCard";
import StatusBadge from "../components/ui/StatusBadge";

function sectionBarData(comp) {
  return [
    { name: "F&G", value: Number(comp?.fg_value || 0) },
    { name: "RSI", value: Number(comp?.rsi_d || 0) },
    { name: "Trend", value: Number(comp?.trend_score || comp?.trend_strength || 42) },
    { name: "BB", value: Number(comp?.bb_score || 68) },
    { name: "Volume", value: Number(comp?.volume_score || 54) },
    { name: "Funding", value: Number(comp?.funding_score || 48) },
  ];
}

function sentimentAccent(sentiment) {
  const key = String(sentiment || "neutral").toLowerCase();
  if (key.includes("bull")) return "#22c55e";
  if (key.includes("bear")) return "#ef4444";
  return "#6b7280";
}

function actionClass(action) {
  const a = String(action || "").toUpperCase();
  if (a === "BUY") return "badge-buy";
  if (a === "SELL") return "badge-sell";
  return "badge-hold";
}

function resultClass(result) {
  const r = String(result || "").toUpperCase();
  if (r === "EXECUTED") return "badge-buy";
  if (r === "SKIP" || r === "HOLD") return "badge-hold";
  return "badge-sell";
}

export default function BtcPage() {
  const { t } = useLang();
  const { data: composite, error: compositeError, loading: compositeLoading } = usePolling(getBtcComposite, 30000);
  const { data: portfolio, loading: portfolioLoading } = usePolling(getBtcPortfolio, 30000);
  const { data: liveActivity } = usePolling(getBtcLiveActivity, 10000);
  const { data: dbTrades, loading: dbTradesLoading } = usePolling(getBtcTrades, 30000);
  const { data: candles, loading: candlesLoading } = usePolling(() => getBtcCandles("minute5", 72), 60000);
  const { data: news } = usePolling(getBtcNews, 120000);
  const { data: filters } = usePolling(getBtcFilters, 30000);

  const candleSeries = useMemo(() => {
    const rows = Array.isArray(candles?.candles) ? candles.candles : Array.isArray(candles) ? candles : [];
    return rows.map((row, index) => ({
      label: row?.time?.slice?.(11, 16) || row?.timestamp?.slice?.(11, 16) || `${index + 1}`,
      value: Number(row?.close ?? row?.trade_price ?? 0),
      open: Number(row?.open ?? row?.opening_price ?? row?.trade_price ?? 0),
      high: Number(row?.high ?? row?.high_price ?? row?.trade_price ?? 0),
      low: Number(row?.low ?? row?.low_price ?? row?.trade_price ?? 0),
      close: Number(row?.close ?? row?.trade_price ?? 0),
      volume: Number(row?.volume ?? row?.candle_acc_trade_volume ?? 0),
    }));
  }, [candles]);

  const currentPosition = portfolio?.open_positions?.[0];
  const btcSummary = portfolio?.summary || {};
  const scoreBars = useMemo(() => sectionBarData(composite), [composite]);
  const sentimentValue = Number(composite?.fg_value || 0);

  // 실행 피드: JSONL 우선, DB fallback
  const execRows = liveActivity?.rows || [];

  // 체결 내역: btc_trades DB (가격/PnL 있음)
  const tradeRows = Array.isArray(dbTrades) ? dbTrades : [];

  const newsRows = news?.items || news || [];
  const filterStats = [
    { label: "Funding", value: filters?.funding_rate ?? 0, suffix: "%", tone: (filters?.funding_rate ?? 0) >= 0 ? "profit" : "loss" },
    { label: "Long/Short", value: filters?.long_short_ratio ?? 0, suffix: "x", tone: "neutral" },
    { label: "Open Interest", value: filters?.open_interest ?? 0, suffix: "", tone: "neutral" },
  ];

  const marketWatch = [
    { symbol: "BTC", last: candleSeries.at(-1)?.close ?? candleSeries.at(-1)?.value ?? 0, delta: currentPosition?.pnl_pct ?? 0, tag: "Live" },
    { symbol: "F&G", last: sentimentValue, delta: composite?.fg_change ?? 0, tag: composite?.fg_label || "Sentiment" },
    { symbol: "Funding", last: filters?.funding_rate ?? 0, delta: 0, tag: "%" },
    { symbol: "OI", last: filters?.open_interest ?? 0, delta: 0, tag: "Open Int" },
  ];
  const [selectedWatch, setSelectedWatch] = useState("BTC");

  const compositeTotal = Number(composite?.composite?.total ?? composite?.total ?? 0);
  const buyThreshold = Number(composite?.buy_threshold ?? 45);

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>{t("BTC Live Trading Desk")}</h1>
          <p>
            {t("Composite score, on-chain filters, live position context, and execution trace in one dense operator view.")}
          </p>
        </div>
        <StatusBadge status={composite?.regime || composite?.trend || "TRANSITION"} />
      </div>

      {compositeError ? <ErrorState message={`BTC API connection failed: ${compositeError}`} /> : null}

      {/* ── 포트폴리오 요약 배너 ── */}
      <div className="portfolio-banner">
        <div className="pf-tile">
          <div className="pf-label">{t("투자금")}</div>
          <div className="pf-value mono">{btcSummary.total_invested ? krw(btcSummary.total_invested) : "—"}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("평가금")}</div>
          <div className="pf-value mono">{(btcSummary.estimated_asset || btcSummary.total_eval) ? krw(btcSummary.estimated_asset || btcSummary.total_eval) : "—"}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("미실현 손익")}</div>
          <div className={`pf-value mono ${Number(btcSummary.unrealized_pnl_pct || 0) >= 0 ? "profit" : "loss"}`}>
            {Number(btcSummary.unrealized_pnl_pct || 0) >= 0 ? "▲ " : "▼ "}{pct(btcSummary.unrealized_pnl_pct || 0)}
            {btcSummary.unrealized_pnl ? ` (${krw(btcSummary.unrealized_pnl)})` : ""}
          </div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("가용 KRW")}</div>
          <div className="pf-value mono">{btcSummary.krw_balance ? krw(btcSummary.krw_balance) : "—"}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("스코어 / 임계")}</div>
          <div className={`pf-value mono ${compositeTotal >= buyThreshold ? "profit" : "loss"}`}>
            {compositeTotal} / {buyThreshold}
          </div>
        </div>
      </div>

      <div className="tv-terminal">
        {/* ── 좌측 레일 ── */}
        <aside className="tv-left-rail">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Watchlist")}</h2>
            </div>
            <div className="rail-list">
              {marketWatch.map((item) => (
                <button
                  key={item.symbol}
                  type="button"
                  className={`watchlist-row ${selectedWatch === item.symbol ? "is-active" : ""}`.trim()}
                  onClick={() => setSelectedWatch(item.symbol)}
                  style={{ color: "inherit", textAlign: "left" }}
                >
                  <strong>{item.symbol}</strong>
                  <span className="mono">
                    {item.symbol === "BTC" ? krw(item.last) : Number(item.last || 0).toLocaleString()}
                  </span>
                  <span className={Number(item.delta || 0) >= 0 ? "profit mono" : "loss mono"}>
                    {pct(item.delta || 0)}
                  </span>
                  <span className="subtle">{item.tag}</span>
                </button>
              ))}
            </div>
          </GlassCard>

          {/* 체결 내역 (btc_trades DB) */}
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("체결 내역")}</h2>
              <Activity size={18} color="var(--text-secondary)" />
            </div>
            {dbTradesLoading ? (
              <LoadingSkeleton height={260} />
            ) : tradeRows.length === 0 ? (
              <EmptyState message={t("No BTC trades recorded.")} />
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {tradeRows.slice(0, 10).map((trade, index) => {
                  const pnl = Number(trade.pnl_pct || 0);
                  return (
                    <div key={trade.id || trade.timestamp || index} style={{ fontSize: 13, borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <span className="mono subtle" style={{ fontSize: 11 }}>
                          {compactTime(trade.timestamp || trade.created_at)}
                        </span>
                        <span className={`trade-badge ${actionClass(trade.action)}`}>
                          {trade.action || "HOLD"}
                        </span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="mono" style={{ fontSize: 12 }}>{krw(trade.price || 0)}</span>
                        <span className={`mono ${pnl >= 0 ? "profit" : "loss"}`} style={{ fontSize: 12 }}>
                          {pnl >= 0 ? "▲ " : "▼ "}{pct(pnl)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </GlassCard>
        </aside>

        {/* ── 메인 콘텐츠 ── */}
        <div className="tv-main tv-stack">
          <GlassCard className="card-pad" accent>
            <div className="symbol-header">
              <div>
                <div className="symbol-code">{selectedWatch === "BTC" ? "BTCKRW" : selectedWatch}</div>
                <div className="symbol-meta">
                  <span className="toolbar-chip mono">{t("Upbit")}</span>
                  <span className="toolbar-chip">{t("Spot")}</span>
                  <span className="toolbar-chip">{t("5m")}</span>
                  <span className="toolbar-chip">{t("Live Feed")}</span>
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="symbol-price">
                  {krw(Number(portfolio?.summary?.btc_price_krw || portfolio?.summary?.btc_price || portfolio?.summary?.current_price || candleSeries.at(-1)?.value || 0))}
                </div>
                <div className={Number(currentPosition?.pnl_pct || 0) >= 0 ? "profit" : "loss"} style={{ marginTop: 6, fontWeight: 700 }}>
                  {pct(currentPosition?.pnl_pct || 0)}
                </div>
              </div>
            </div>
            {candlesLoading ? <LoadingSkeleton height={420} /> : (
              <ErrorBoundary>
                <LightweightPriceChart data={candleSeries} />
              </ErrorBoundary>
            )}
          </GlassCard>

          <div className="split-2">
            {/* 실행 피드 (JSONL) */}
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>{t("실행 피드")}</h2>
                <CandlestickChart size={18} color="var(--text-secondary)" />
              </div>
              <div className="stack" style={{ gap: 10 }}>
                {execRows.slice(0, 8).map((row, index) => (
                  <div
                    key={row.id || row.timestamp_kst || index}
                    style={{
                      borderRadius: 8,
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid rgba(255,255,255,0.05)",
                      padding: "10px 12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <span className="mono subtle" style={{ fontSize: 12 }}>
                        {compactTime(row.timestamp_kst || row.timestamp || row.created_at)}
                      </span>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <span className={`trade-badge ${actionClass(row.action)}`}>{row.action || "HOLD"}</span>
                        <span className={`trade-badge ${resultClass(row.result)}`}>{row.result || "—"}</span>
                        {typeof row.confidence === "number" && (
                          <span className="mono subtle" style={{ fontSize: 11 }}>{Math.round(row.confidence)}%</span>
                        )}
                      </div>
                    </div>
                    {row.message ? (
                      <div className="subtle" style={{ fontSize: 12, lineHeight: 1.5 }}>
                        {row.message}
                      </div>
                    ) : null}
                  </div>
                ))}
                {execRows.length === 0 ? <EmptyState message={t("No execution feed data.")} /> : null}
              </div>
            </GlassCard>

            {/* 뉴스 피드 */}
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>{t("News Feed")}</h2>
                <Newspaper size={18} color="var(--text-secondary)" />
              </div>
              <div className="stack" style={{ gap: 12 }}>
                {newsRows.slice(0, 6).map((item, index) => (
                  <div
                    key={item.id || item.url || index}
                    className="news-item"
                    style={{ "--news-accent": sentimentAccent(item.sentiment) }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
                      <strong style={{ fontSize: 14 }}>{item.title || item.headline || "Untitled headline"}</strong>
                      <span className="pill sentiment-pill">{item.sentiment || "Neutral"}</span>
                    </div>
                    <div className="subtle" style={{ fontSize: 13, display: "flex", justifyContent: "space-between" }}>
                      <span>{item.source || item.domain || "CryptoPanic"}</span>
                      {item.published_at || item.timestamp ? (
                        <span className="mono" style={{ fontSize: 11 }}>{compactTime(item.published_at || item.timestamp)}</span>
                      ) : null}
                    </div>
                  </div>
                ))}
                {newsRows.length === 0 ? <EmptyState message={t("No BTC news available.")} /> : null}
              </div>
            </GlassCard>
          </div>
        </div>

        {/* ── 우측 사이드바 ── */}
        <aside className="tv-side">
          {/* 컴포짓 스코어 + 시그널 바 */}
          <GlassCard className="card-pad" accent>
            <div className="panel-title">
              <h2>{t("Composite Score")}</h2>
              <Bitcoin size={18} color="var(--text-secondary)" />
            </div>
            {compositeLoading ? (
              <LoadingSkeleton height={280} />
            ) : (
              <>
                <CircularGauge
                  value={compositeTotal}
                  label="Score"
                  subtitle={`임계 ${buyThreshold}`}
                  size={190}
                />
                <div className="score-list" style={{ marginTop: 16 }}>
                  {scoreBars.map((bar) => (
                    <div key={bar.name}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                        <span className="subtle">{bar.name}</span>
                        <span className="mono">{bar.value}</span>
                      </div>
                      <div className="signal-bar">
                        <div
                          className="signal-bar-fill"
                          style={{
                            width: `${Math.min(Math.max(bar.value, 0), 100)}%`,
                            opacity: bar.value < 35 ? 0.35 : 1,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </GlassCard>

          {/* 포지션 */}
          <GlassCard
            className={`card-pad ${currentPosition ? (Number(currentPosition.pnl_pct || 0) >= 0 ? "glass-card--profit" : "glass-card--loss") : ""}`.trim()}
          >
            <div className="panel-title">
              <h2>{t("Position")}</h2>
              <ShieldCheck size={18} color="var(--text-secondary)" />
            </div>
            {portfolioLoading ? (
              <LoadingSkeleton height={220} />
            ) : currentPosition ? (
              <div className="tabular-list">
                <div className="kv-row"><span className="subtle">Entry</span><span className="mono">{krw(currentPosition.entry_price || 0)}</span></div>
                <div className="kv-row"><span className="subtle">Current</span><span className="mono">{krw(currentPosition.current_price_krw || currentPosition.current_price || currentPosition.market_price || 0)}</span></div>
                <div className="kv-row"><span className="subtle">PnL</span><span className={Number(currentPosition.pnl_pct || 0) >= 0 ? "profit mono glow-profit" : "loss mono glow-loss"}>{pct(currentPosition.pnl_pct || 0)}</span></div>
                <div className="kv-row"><span className="subtle">Size</span><span className="mono">{currentPosition.quantity || currentPosition.size || "--"}</span></div>
                <div className="kv-row"><span className="subtle">Side</span><span className="mono">{currentPosition.side || currentPosition.position_side || "OPEN"}</span></div>
              </div>
            ) : (
              <EmptyState message={t("No active BTC position.")} />
            )}
          </GlassCard>

          {/* 센티먼트 & 필터 */}
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Sentiment & Filters")}</h2>
              <Radar size={18} color="var(--text-secondary)" />
            </div>
            <CircularGauge value={sentimentValue} label="F&G" subtitle={composite?.fg_label || "Sentiment"} size={170} />
            <div className="tv-section">
              {filterStats.map((item) => (
                <StatCard
                  key={item.label}
                  label={item.label}
                  value={Number(item.value || 0)}
                  suffix={item.suffix}
                  trend={sparkline([item.value || 0, item.value || 0])}
                  delta={0}
                  tone={item.tone}
                  icon={<CandlestickChart size={18} />}
                />
              ))}
            </div>
          </GlassCard>
        </aside>
      </div>
    </div>
  );
}
