import { DollarSign, Globe2, Landmark, Sigma, TrendingUp } from "lucide-react";
import { getUsFx, getUsMarket, getUsPositions, getUsTrades } from "../api";
import usePolling from "../hooks/usePolling";
import { compactTime, pct, usd } from "../lib/format";
import DeferredRender from "../components/ui/DeferredRender";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState } from "../components/ui/PageState";
import SvgRadarChart from "../components/ui/SvgRadarChart";

const factorData = [
  { factor: "Momentum", value: 78 },
  { factor: "Volume", value: 66 },
  { factor: "52W High", value: 59 },
  { factor: "Risk", value: 42 },
  { factor: "Macro", value: 55 },
];

export default function UsStockPage() {
  const { data: market, loading: marketLoading } = usePolling(getUsMarket, 60000);
  const { data: fx } = usePolling(getUsFx, 60000);
  const { data: positions, loading: positionsLoading } = usePolling(getUsPositions, 30000);
  const { data: trades } = usePolling(getUsTrades, 30000);

  const marketCards = [
    { label: "S&P 500", value: market?.sp500 ?? market?.spx ?? 0, delta: Number(market?.sp500_change_pct || 0) },
    { label: "NASDAQ", value: market?.nasdaq ?? market?.ndx ?? 0, delta: Number(market?.nasdaq_change_pct || 0) },
    { label: "DJI", value: market?.dji ?? market?.dow ?? 0, delta: Number(market?.dji_change_pct || 0) },
  ];

  const ranking = market?.top || market?.momentum || [];
  const openPositions = positions?.positions || positions?.open_positions || [];

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>US Momentum Command</h1>
          <p>Dry-run market monitor for index context, factor-weighted ranking, and simulated portfolio tracking.</p>
        </div>
      </div>

      <div className="page-grid">
        <div className="col-8">
          <div className="grid-4">
            {marketCards.map((card) => (
              <GlassCard key={card.label} className="card-pad">
                <div className="subtle" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  {card.label}
                </div>
                <div style={{ fontSize: 28, fontWeight: 800, marginTop: 12 }}>{Number(card.value || 0).toLocaleString()}</div>
                <div className={card.delta >= 0 ? "profit" : "loss"} style={{ marginTop: 10, fontWeight: 700 }}>
                  {pct(card.delta)}
                </div>
              </GlassCard>
            ))}
          </div>
        </div>

        <div className="col-4">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>USD/KRW FX</h2>
              <DollarSign size={18} color="var(--text-secondary)" />
            </div>
            <div style={{ fontSize: 34, fontWeight: 800 }}>{Number(fx?.rate || fx?.usdkrw || 0).toLocaleString()}</div>
            <div className={Number(fx?.change_pct || 0) >= 0 ? "profit" : "loss"} style={{ marginTop: 10, fontWeight: 700 }}>
              {pct(fx?.change_pct || 0)}
            </div>
          </GlassCard>
        </div>

        <div className="col-7">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Momentum Ranking</h2>
              <TrendingUp size={18} color="var(--text-secondary)" />
            </div>
            {marketLoading ? (
              <LoadingSkeleton height={320} />
            ) : (
              <div className="table-shell">
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>5d</th>
                      <th>20d</th>
                      <th>Volume</th>
                      <th>Near High</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(ranking || []).slice(0, 10).map((row, index) => (
                      <tr key={row.symbol || index}>
                        <td>{row.symbol}</td>
                        <td className={Number(row.ret_5d || 0) >= 0 ? "profit" : "loss"}>{pct(row.ret_5d || 0)}</td>
                        <td className={Number(row.ret_20d || 0) >= 0 ? "profit" : "loss"}>{pct(row.ret_20d || 0)}</td>
                        <td>{Number(row.volume_ratio || 0).toFixed(2)}x</td>
                        <td>{Number(row.near_high || row.high_proximity || 0).toFixed(1)}%</td>
                        <td>{Number(row.score || 0).toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </GlassCard>
        </div>

        <div className="col-5">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>DRY-RUN Portfolio</h2>
              <Landmark size={18} color="var(--text-secondary)" />
            </div>
            {positionsLoading ? (
              <LoadingSkeleton height={320} />
            ) : openPositions.length === 0 ? (
              <EmptyState message="No DRY-RUN positions." />
            ) : (
              <div className="stack" style={{ gap: 12 }}>
                {openPositions.slice(0, 8).map((row, index) => (
                  <div
                    key={row.symbol || row.id || index}
                    style={{
                      padding: 14,
                      borderRadius: 16,
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.05)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                      <strong>{row.symbol || row.stock_code}</strong>
                      <span className={Number(row.pnl_pct || 0) >= 0 ? "profit" : "loss"}>{pct(row.pnl_pct || 0)}</span>
                    </div>
                    <div className="subtle">
                      Qty {row.quantity || 0} · Entry {usd(row.entry_price || row.price)} · Value{" "}
                      {usd(row.market_value || row.current_value)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>

        <div className="col-12">
          <div className="grid-2">
            <DeferredRender height={320}>
              <GlassCard className="card-pad">
                <div className="panel-title">
                  <h2>Market Regime & Factor Weights</h2>
                  <Sigma size={18} color="var(--text-secondary)" />
                </div>
                <SvgRadarChart data={factorData} size={320} />
              </GlassCard>
            </DeferredRender>

            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>Recent Simulated Executions</h2>
                <Globe2 size={18} color="var(--text-secondary)" />
              </div>
              <div className="stack" style={{ gap: 12 }}>
                {(trades || []).slice(0, 8).map((trade, index) => (
                  <div
                    key={trade.id || index}
                    style={{
                      padding: 14,
                      borderRadius: 16,
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.05)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <strong>{trade.symbol || "US"}</strong>
                      <span>{compactTime(trade.timestamp || trade.created_at)}</span>
                    </div>
                    <div className={String(trade.action || trade.trade_type).toUpperCase() === "BUY" ? "profit" : "loss"}>
                      {trade.action || trade.trade_type || "HOLD"} · {usd(trade.price)} · Qty {trade.quantity || 0}
                    </div>
                  </div>
                ))}
                {(trades || []).length === 0 ? <EmptyState message="No simulated US trades yet." /> : null}
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
    </div>
  );
}
