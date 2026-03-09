import { Brain, BriefcaseBusiness, Landmark, ListOrdered, ShieldEllipsis, History } from "lucide-react";
import { useMemo } from "react";
import {
  getKrTop,
  getStockPortfolio,
  getStockStrategy,
  getStockTrades,
} from "../api";
import usePolling from "../hooks/usePolling";
import { compactTime, krw, pct } from "../lib/format";
import DeferredRender from "../components/ui/DeferredRender";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState } from "../components/ui/PageState";
import StatCard from "../components/ui/StatCard";
import SvgBarChart from "../components/ui/SvgBarChart";
import SvgDonutChart from "../components/ui/SvgDonutChart";

const COLORS = ["#8b5cf6", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#14b8a6"];

export default function KrStockPage() {
  const { data: portfolio, loading: portfolioLoading } = usePolling(getStockPortfolio, 30000);
  const { data: topStocks, loading: topLoading } = usePolling(getKrTop, 60000);
  const { data: trades, loading: tradesLoading } = usePolling(getStockTrades, 30000);
  const { data: strategy } = usePolling(getStockStrategy, 60000);

  const positions = portfolio?.positions || portfolio?.holdings || [];
  const donutData = positions.map((row) => ({
    name: row.stock_name || row.name || row.stock_code,
    value: Number(row.weight || row.evaluation_amount || row.market_value || 0),
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

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>KR Stocks Portfolio Lab</h1>
          <p>Paper-trading workspace for Kiwoom-connected portfolio control, ML conviction, and ranked momentum selection.</p>
        </div>
      </div>

      <div className="page-grid">
        <div className="col-4">
          <DeferredRender height={360}>
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>Portfolio Allocation</h2>
                <Landmark size={18} color="var(--text-secondary)" />
              </div>
              {portfolioLoading ? (
                <LoadingSkeleton height={360} />
              ) : donutData.length === 0 ? (
                <EmptyState message="No KR positions available." />
              ) : (
                <SvgDonutChart data={donutData} colors={COLORS} />
              )}
            </GlassCard>
          </DeferredRender>
        </div>

        <div className="col-8">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Current Holdings</h2>
              <BriefcaseBusiness size={18} color="var(--text-secondary)" />
            </div>
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Qty</th>
                    <th>Avg</th>
                    <th>Now</th>
                    <th>PnL</th>
                    <th>Factor Score</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.slice(0, 10).map((row, index) => {
                    const pnl = Number(row.pnl_pct || row.return_pct || 0);
                    const factor = Number(row.factor_score || row.score || 0);
                    return (
                      <tr key={row.stock_code || index}>
                        <td>
                          <div>{row.stock_name || row.name || row.stock_code}</div>
                          <div className="subtle mono" style={{ fontSize: 12 }}>
                            {row.stock_code || "—"}
                          </div>
                        </td>
                        <td>{row.quantity || row.qty || 0}</td>
                        <td>{krw(row.avg_price || row.purchase_price)}</td>
                        <td>{krw(row.current_price || row.price)}</td>
                        <td className={pnl >= 0 ? "profit" : "loss"}>{pct(pnl)}</td>
                        <td>
                          <div style={{ display: "grid", gap: 6 }}>
                            <div className="mono">{factor}</div>
                            <div
                              style={{
                                height: 8,
                                borderRadius: 999,
                                background: "rgba(255,255,255,0.06)",
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  width: `${Math.min(Math.max(factor, 0), 100)}%`,
                                  height: "100%",
                                  background: "var(--gradient-main)",
                                }}
                              />
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </div>

        <div className="col-4">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>ML Signals</h2>
              <Brain size={18} color="var(--text-secondary)" />
            </div>
            <div className="stack" style={{ gap: 14 }}>
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
        </div>

        <div className="col-8">
          <DeferredRender height={320}>
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>Top Momentum Ranking</h2>
                <ListOrdered size={18} color="var(--text-secondary)" />
              </div>
              {topLoading ? (
                <LoadingSkeleton height={320} />
              ) : (
                <SvgBarChart
                  data={(topStocks || []).slice(0, 10).map((row) => ({
                    label: row.stock_code,
                    value: Number(row.score || 0),
                  }))}
                  color="#8b5cf6"
                  height={320}
                />
              )}
            </GlassCard>
          </DeferredRender>
        </div>

        <div className="col-12">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Trade Timeline</h2>
              <History size={18} color="var(--text-secondary)" />
            </div>
            {tradesLoading ? (
              <LoadingSkeleton height={240} />
            ) : (
              <div className="stack" style={{ gap: 12 }}>
                {(trades || []).slice(0, 10).map((trade, index) => {
                  const action = String(trade.trade_type || trade.action || "").toUpperCase();
                  return (
                    <div
                      key={trade.trade_id || index}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "160px 120px 1fr",
                        gap: 16,
                        alignItems: "center",
                        padding: 14,
                        borderRadius: 16,
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.05)",
                      }}
                    >
                      <div className="mono subtle">{compactTime(trade.created_at)}</div>
                      <div className={action === "BUY" ? "profit" : "loss"} style={{ fontWeight: 700 }}>
                        {action || "HOLD"}
                      </div>
                      <div>
                        {trade.stock_name || trade.stock_code || "Unknown"} · {krw(trade.price)} ·{" "}
                        <span className={Number(trade.pnl_pct || 0) >= 0 ? "profit" : "loss"}>
                          {pct(trade.pnl_pct || 0)}
                        </span>
                      </div>
                    </div>
                  );
                })}
                {(trades || []).length === 0 ? <EmptyState message="No KR trade timeline entries." /> : null}
              </div>
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
