import { Brain, BriefcaseBusiness, Landmark, ListOrdered, ShieldEllipsis, History } from "lucide-react";
import { useMemo, useState } from "react";
import {
  getKrPortfolio,
  getKrTop,
  getStockPortfolio,
  getStockStrategy,
  getStockChart,
  getStockTrades,
} from "../api";
import usePolling from "../hooks/usePolling";
import { useLang } from "../hooks/useLang";
import { compactTime, krw, pct } from "../lib/format";
import DeferredRender from "../components/ui/DeferredRender";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState } from "../components/ui/PageState";
import ErrorBoundary from "../components/ui/ErrorBoundary";
import StatCard from "../components/ui/StatCard";
import SvgDonutChart from "../components/ui/SvgDonutChart";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";

const COLORS = ["#8b5cf6", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#14b8a6"];

export default function KrStockPage() {
  const { t } = useLang();
  const { data: portfolio, loading: portfolioLoading } = usePolling(getStockPortfolio, 30000);
  const { data: krPortfolio } = usePolling(getKrPortfolio, 30000);
  const { data: topStocks, loading: topLoading } = usePolling(getKrTop, 60000);
  const { data: trades, loading: tradesLoading } = usePolling(getStockTrades, 30000);
  const { data: strategy } = usePolling(getStockStrategy, 60000);

  // krPortfolio(Supabase 기반)를 우선, 키움 portfolio는 fallback
  const positions = krPortfolio?.open_positions?.length
    ? krPortfolio.open_positions
    : portfolio?.positions || portfolio?.holdings || [];
  const krSummary = krPortfolio?.summary || {};
  const donutData = positions.map((row) => ({
    name: row.stock_name || row.name || row.code || row.stock_code,
    value: Number(row.evaluation || row.weight || row.evaluation_amount || row.market_value || 0),
  }));
  const mlSignals = useMemo(
    () => [
      { label: "Prediction", value: Number(strategy?.ml_prediction || 63), suffix: "%", delta: 4.6, tone: "profit" },
      { label: "Confidence", value: Number(strategy?.confidence || 71), suffix: "%", delta: 2.4, tone: "profit" },
      { label: "Risk Score", value: Number(strategy?.risk_score || 38), suffix: "", delta: -1.2, tone: "loss" },
      { label: "SHAP Rank", value: Number(strategy?.shap_strength || 5), suffix: "", delta: 0.8, tone: "neutral" },
    ],
    [strategy],
  );
  const watchRows = (topStocks || []).slice(0, 8).map((row) => ({
    symbol: row.stock_code || row.symbol,
    score: Number(row.score || 0),
    delta: Number(row.momentum || row.ret_20d || 0),
    tag: row.grade || "A",
  }));
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const activeSymbol = selectedSymbol || watchRows[0]?.symbol || positions[0]?.stock_code || null;
  const activeTop = (topStocks || []).find((row) => (row.stock_code || row.symbol) === activeSymbol) || topStocks?.[0];
  const activePosition = positions.find((row) => (row.stock_code || row.symbol) === activeSymbol) || positions[0];
  const { data: chartData, loading: chartLoading } = usePolling(
    () => activeSymbol ? getStockChart(activeSymbol, "1d") : Promise.resolve(null),
    60000,
    [activeSymbol],
  );
  const activeCurve = useMemo(() => {
    const base = Number(activeTop?.score || activePosition?.factor_score || 50);
    return [
      { label: "D-5", value: Math.max(base - 18, 8) },
      { label: "D-4", value: Math.max(base - 10, 12) },
      { label: "D-3", value: Math.max(base - 6, 16) },
      { label: "D-2", value: Math.max(base - 2, 20) },
      { label: "D-1", value: Math.max(base + 4, 24) },
      { label: "Now", value: base },
    ];
  }, [activeTop, activePosition]);
  const chartSeries = useMemo(
    () => (chartData?.candles || []).map((row) => ({
      time: row.time || row.date,
      open: Number(row.open || row.open_price || row.close || 0),
      high: Number(row.high || row.high_price || row.close || 0),
      low: Number(row.low || row.low_price || row.close || 0),
      close: Number(row.close || row.close_price || 0),
      volume: Number(row.volume || 0),
      value: Number(row.close || row.close_price || 0),
    })),
    [chartData],
  );

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>{t("KR Stocks Portfolio Lab")}</h1>
          <p>{t("Paper-trading workspace for Kiwoom-connected portfolio control, ML conviction, and ranked momentum selection.")}</p>
        </div>
      </div>

      {!portfolioLoading && positions.length === 0 && !krPortfolio?.open_positions?.length && (
        <div
          style={{
            padding: "10px 16px",
            borderRadius: 10,
            background: "rgba(245,158,11,0.1)",
            border: "1px solid rgba(245,158,11,0.25)",
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 13,
            color: "var(--warning)",
          }}
        >
          ⚠ {t("키움 연결 오프라인 또는 보유 종목 없음")}
        </div>
      )}

      {/* ── 포트폴리오 요약 배너 ── */}
      <div className="portfolio-banner">
        <div className="pf-tile">
          <div className="pf-label">{t("투자금")}</div>
          <div className="pf-value mono">{krw(krSummary.total_invested || portfolio?.total_purchase || 0)}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("평가금")}</div>
          <div className="pf-value mono">{krw(krSummary.total_eval || portfolio?.total_evaluation || 0)}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("미실현 손익")}</div>
          <div className={`pf-value mono ${Number(krSummary.unrealized_pnl || 0) >= 0 ? "profit" : "loss"}`}>
            {krSummary.total_invested
              ? pct(((krSummary.total_eval - krSummary.total_invested) / krSummary.total_invested) * 100)
              : "—"}
            {krSummary.unrealized_pnl ? ` (${krw(krSummary.unrealized_pnl)})` : ""}
          </div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("가용 KRW")}</div>
          <div className="pf-value mono">{krw(krSummary.krw_balance || portfolio?.deposit || 0)}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">{t("보유 종목")}</div>
          <div className="pf-value mono">{positions.length}종목</div>
        </div>
      </div>

      <div className="tv-terminal">
        <aside className="tv-left-rail">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Watchlist")}</h2>
            </div>
            <div className="rail-list">
              {watchRows.map((row) => (
                <button
                  key={row.symbol}
                  type="button"
                  className={`watchlist-row ${activeSymbol === row.symbol ? "is-active" : ""}`.trim()}
                  onClick={() => setSelectedSymbol(row.symbol)}
                  style={{ color: "inherit", textAlign: "left" }}
                >
                  <strong>{row.symbol}</strong>
                  <span className="mono">{row.score.toFixed(0)}</span>
                  <span className={row.delta >= 0 ? "profit mono" : "loss mono"}>{pct(row.delta)}</span>
                  <span className="subtle">{row.tag}</span>
                </button>
              ))}
              {watchRows.length === 0 ? <EmptyState message={t("No KR symbols.")} /> : null}
            </div>
          </GlassCard>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Strategy Bias")}</h2>
            </div>
            <div className="tabular-list">
              <div className="kv-row"><span className="subtle">{t("Rule Weight")}</span><span className="mono">60%</span></div>
              <div className="kv-row"><span className="subtle">{t("ML Weight")}</span><span className="mono">40%</span></div>
              <div className="kv-row"><span className="subtle">{t("Confidence")}</span><span className="mono">{Number(strategy?.confidence || 71).toFixed(0)}%</span></div>
              <div className="kv-row"><span className="subtle">{t("Risk Score")}</span><span className="mono">{Number(strategy?.risk_score || 38).toFixed(0)}</span></div>
            </div>
          </GlassCard>
        </aside>

        <div className="tv-main tv-stack">
          <DeferredRender height={320}>
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>{t("Momentum Curve")}</h2>
                <ListOrdered size={18} color="var(--text-secondary)" />
              </div>
              {chartLoading ? (
                <LoadingSkeleton height={300} />
              ) : (
                <ErrorBoundary>
                  <LightweightPriceChart data={chartSeries} />
                </ErrorBoundary>
              )}
            </GlassCard>
          </DeferredRender>

          <GlassCard className="card-pad">
            <div className="symbol-header">
              <div>
                <div className="symbol-code">{activeSymbol}</div>
                <div className="symbol-meta">
                  <span className="toolbar-chip">{t("KOSPI/KOSDAQ")}</span>
                  <span className="toolbar-chip">{t("Paper Trading")}</span>
                  <span className="toolbar-chip mono">{activeTop?.grade || "A"}</span>
                </div>
              </div>
            </div>
            <div className="panel-title">
              <h2>{t("Current Holdings")}</h2>
              <BriefcaseBusiness size={18} color="var(--text-secondary)" />
            </div>
            <div className="table-shell">
              <table>
                <caption className="sr-only">{t("KR stock holdings table")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("Name")}</th>
                    <th scope="col">{t("Qty")}</th>
                    <th scope="col">{t("Avg")}</th>
                    <th scope="col">{t("Now")}</th>
                    <th scope="col">{t("PnL")}</th>
                    <th scope="col">{t("Factor")}</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.slice(0, 12).map((row, index) => {
                    const pnl = Number(row.pnl_pct || row.return_pct || 0);
                    const factor = Number(row.factor_score || row.score || 0);
                    return (
                      <tr key={row.stock_code || index} className={(row.stock_code || row.symbol) === activeSymbol ? "is-active" : ""}>
                        <td>
                          <div>{row.stock_name || row.name || row.stock_code}</div>
                          <div className="subtle mono" style={{ fontSize: 12 }}>{row.stock_code || "—"}</div>
                        </td>
                        <td>{row.quantity || row.qty || 0}</td>
                        <td>{krw(row.avg_entry || row.price || row.avg_price || row.purchase_price)}</td>
                        <td>{krw(row.current_price || 0)}</td>
                        <td className={pnl >= 0 ? "profit mono" : "loss mono"}>{pnl >= 0 ? "▲ " : "▼ "}{pct(pnl)}</td>
                        <td className="mono">{factor.toFixed(0)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </GlassCard>

          <div className="split-2">
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>{t("Top Momentum Ranking")}</h2>
                <ListOrdered size={18} color="var(--text-secondary)" />
              </div>
              {topLoading ? (
                <LoadingSkeleton height={320} />
              ) : (
                <div className="tabular-list">
                  {(topStocks || []).slice(0, 10).map((row, index) => (
                    <button
                      key={row.stock_code || index}
                      type="button"
                      className={`watchlist-row ${activeSymbol === row.stock_code ? "is-active" : ""}`.trim()}
                      onClick={() => setSelectedSymbol(row.stock_code)}
                      style={{ color: "inherit", textAlign: "left" }}
                    >
                      <strong>{row.stock_code}</strong>
                      <span className="mono">{Number(row.score || 0).toFixed(0)}</span>
                      <span className={Number(row.momentum || row.ret_20d || 0) >= 0 ? "profit mono" : "loss mono"}>
                        {pct(row.momentum || row.ret_20d || 0)}
                      </span>
                      <span className="subtle">{row.grade || "A"}</span>
                    </button>
                  ))}
                </div>
              )}
            </GlassCard>

            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>{t("Trade Timeline")}</h2>
                <History size={18} color="var(--text-secondary)" />
              </div>
              {tradesLoading ? (
                <LoadingSkeleton height={320} />
              ) : (
                <div className="stack" style={{ gap: 12 }}>
                  {(trades || []).slice(0, 8).map((trade, index) => {
                    const action = String(trade.trade_type || trade.action || "").toUpperCase();
                    return (
                      <div key={trade.trade_id || index} className="timeline-row" style={{ gridTemplateColumns: "140px 90px 1fr", borderColor: (trade.stock_code || trade.symbol) === activeSymbol ? "rgba(139,92,246,0.35)" : undefined }}>
                        <div className="mono subtle">{compactTime(trade.created_at)}</div>
                        <div className={action === "BUY" ? "profit" : "loss"} style={{ fontWeight: 700 }}>{action || "HOLD"}</div>
                        <div>
                          {trade.stock_name || trade.stock_code || "Unknown"} · {krw(trade.price)} ·{" "}
                          <span className={Number(trade.pnl_pct || 0) >= 0 ? "profit mono" : "loss mono"}>{pct(trade.pnl_pct || 0)}</span>
                        </div>
                      </div>
                    );
                  })}
                  {(trades || []).length === 0 ? <EmptyState message={t("No KR trade timeline entries.")} /> : null}
                </div>
              )}
            </GlassCard>
          </div>
        </div>

        <aside className="tv-side">
          <DeferredRender height={360}>
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>{t("Portfolio Allocation")}</h2>
                <Landmark size={18} color="var(--text-secondary)" />
              </div>
              {portfolioLoading ? (
                <LoadingSkeleton height={360} />
              ) : donutData.length === 0 ? (
                <EmptyState message={t("No KR positions available.")} />
              ) : (
                <SvgDonutChart data={donutData} colors={COLORS} />
              )}
            </GlassCard>
          </DeferredRender>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("ML Signals")}</h2>
              <Brain size={18} color="var(--text-secondary)" />
            </div>
            <div className="tv-section">
              {mlSignals.map((signal) => (
                <StatCard
                  key={signal.label}
                  label={signal.label}
                  value={signal.value}
                  suffix={signal.suffix}
                  delta={signal.delta}
                  trend={[{ value: signal.value * 0.76 }, { value: signal.value }]}
                  tone={signal.tone}
                  icon={<ShieldEllipsis size={18} />}
                />
              ))}
            </div>
          </GlassCard>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Selection Summary")}</h2>
            </div>
            <div className="tabular-list">
              <div className="kv-row"><span className="subtle">{t("Selected")}</span><span className="mono">{activeSymbol}</span></div>
              <div className="kv-row"><span className="subtle">{t("Grade")}</span><span className="mono">{activeTop?.grade || "A"}</span></div>
              <div className="kv-row"><span className="subtle">{t("Score")}</span><span className="mono">{Number(activeTop?.score || activePosition?.factor_score || 0).toFixed(0)}</span></div>
              <div className="kv-row"><span className="subtle">{t("PnL")}</span><span className={Number(activePosition?.pnl_pct || activePosition?.return_pct || activeTop?.momentum || 0) >= 0 ? "profit mono" : "loss mono"}>{pct(activePosition?.pnl_pct || activePosition?.return_pct || activeTop?.momentum || 0)}</span></div>
            </div>
          </GlassCard>
        </aside>
      </div>
    </div>
  );
}
