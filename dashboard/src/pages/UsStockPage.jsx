import { useState } from "react";
import { DollarSign, Globe2, Landmark, Sigma, TrendingUp } from "lucide-react";
import { getUsChart, getUsFx, getUsMarket, getUsPortfolio, getUsPositions, getUsTrades } from "../api";
import usePolling from "../hooks/usePolling";
import { compactTime, pct, usd } from "../lib/format";
import DeferredRender from "../components/ui/DeferredRender";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState } from "../components/ui/PageState";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
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
  const { data: usPortfolio } = usePolling(getUsPortfolio, 30000);
  const { data: positions, loading: positionsLoading } = usePolling(getUsPositions, 30000);
  const { data: trades } = usePolling(getUsTrades, 30000);

  const usSummary = usPortfolio?.summary || {};

  const marketCards = [
    { label: "S&P 500", value: market?.sp500 ?? market?.spx ?? 0, delta: Number(market?.sp500_change_pct || 0) },
    { label: "NASDAQ", value: market?.nasdaq ?? market?.ndx ?? 0, delta: Number(market?.nasdaq_change_pct || 0) },
    { label: "DJI", value: market?.dji ?? market?.dow ?? 0, delta: Number(market?.dji_change_pct || 0) },
  ];

  const ranking = market?.top || market?.momentum || [];
  const openPositions = positions?.positions || positions?.open_positions || [];
  const watchRows = ranking.slice(0, 8).map((row) => ({
    symbol: row.symbol,
    score: Number(row.score || 0),
    delta: Number(row.ret_20d || 0),
    tag: Number(row.volume_ratio || 0).toFixed(1) + "x",
  }));
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const activeSymbol = selectedSymbol || watchRows[0]?.symbol || "US MOMENTUM";
  const activeRank = ranking.find((row) => row.symbol === activeSymbol) || ranking[0];
  const activePosition = openPositions.find((row) => (row.symbol || row.stock_code) === activeSymbol) || openPositions[0];
  const { data: chartData, loading: chartLoading } = usePolling(
    () => getUsChart(activeSymbol, "3mo"),
    60000,
    [activeSymbol],
  );
  const activeCurve = [
    { label: "D-5", value: Math.max(Number(activeRank?.score || 55) - 16, 10) },
    { label: "D-4", value: Math.max(Number(activeRank?.score || 55) - 9, 15) },
    { label: "D-3", value: Math.max(Number(activeRank?.score || 55) - 4, 18) },
    { label: "D-2", value: Math.max(Number(activeRank?.score || 55) + 1, 20) },
    { label: "D-1", value: Math.max(Number(activeRank?.score || 55) + 5, 25) },
    { label: "Now", value: Number(activeRank?.score || 55) },
  ];
  const chartSeries = (chartData?.candles || []).map((row) => ({
    time: row.time,
    open: Number(row.open || 0),
    high: Number(row.high || 0),
    low: Number(row.low || 0),
    close: Number(row.close || 0),
    volume: Number(row.volume || 0),
    value: Number(row.close || 0),
  }));

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>US Momentum Command</h1>
          <p>Dry-run market monitor for index context, factor-weighted ranking, and simulated portfolio tracking.</p>
        </div>
      </div>

      {/* ── 포트폴리오 요약 배너 ── */}
      <div className="portfolio-banner">
        <div className="pf-tile">
          <div className="pf-label">투자금 (USD)</div>
          <div className="pf-value mono">{usd(usSummary.total_invested || 0)}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">평가금 (USD)</div>
          <div className="pf-value mono">{usd(usSummary.total_current || 0)}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">미실현 손익</div>
          <div className={`pf-value mono ${Number(usSummary.unrealized_pnl_pct || 0) >= 0 ? "profit" : "loss"}`}>
            {pct(usSummary.unrealized_pnl_pct || 0)}
            {usSummary.unrealized_pnl ? ` (${usd(usSummary.unrealized_pnl)})` : ""}
          </div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">환율 (USD/KRW)</div>
          <div className="pf-value mono">{Number(fx?.rate || fx?.usdkrw || 0).toLocaleString()}</div>
        </div>
        <div className="pf-tile">
          <div className="pf-label">오픈 포지션</div>
          <div className="pf-value mono">{openPositions.length}개</div>
        </div>
      </div>

      <div className="tv-terminal">
        <aside className="tv-left-rail">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Watchlist</h2>
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
              {watchRows.length === 0 ? <EmptyState message="No US symbols." /> : null}
            </div>
          </GlassCard>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Market Pulse</h2>
            </div>
            <div className="tabular-list">
              {marketCards.map((card) => (
                <div key={card.label} className="kv-row">
                  <span className="subtle">{card.label}</span>
                  <span className={card.delta >= 0 ? "profit mono" : "loss mono"}>{pct(card.delta)}</span>
                </div>
              ))}
              <div className="kv-row">
                <span className="subtle">USD/KRW</span>
                <span className="mono">{Number(fx?.rate || fx?.usdkrw || 0).toLocaleString()}</span>
              </div>
            </div>
          </GlassCard>
        </aside>

        <div className="tv-main tv-stack">
          <DeferredRender height={320}>
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>Momentum Curve</h2>
                <TrendingUp size={18} color="var(--text-secondary)" />
              </div>
              {chartLoading || marketLoading ? (
                <LoadingSkeleton height={300} />
              ) : (
                <LightweightPriceChart title={`${activeSymbol} Price`} data={chartSeries.length > 0 ? chartSeries : activeCurve} />
              )}
            </GlassCard>
          </DeferredRender>

          <div className="market-strip">
            {marketCards.map((card) => (
              <GlassCard key={card.label} className="market-tile">
                <div className="subtle" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  {card.label}
                </div>
                <div className="mono" style={{ fontSize: 28, fontWeight: 800, marginTop: 12 }}>{Number(card.value || 0).toLocaleString()}</div>
                <div className={card.delta >= 0 ? "profit" : "loss"} style={{ marginTop: 10, fontWeight: 700 }}>
                  {pct(card.delta)}
                </div>
              </GlassCard>
            ))}
          </div>

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

          <GlassCard className="card-pad">
            <div className="symbol-header">
              <div>
                <div className="symbol-code">{activeSymbol}</div>
                <div className="symbol-meta">
                  <span className="toolbar-chip">US Universe</span>
                  <span className="toolbar-chip">Dry Run</span>
                  <span className="toolbar-chip mono">{activeRank?.volume_ratio ? `${Number(activeRank.volume_ratio).toFixed(1)}x vol` : `${ranking.length} Symbols`}</span>
                </div>
              </div>
            </div>
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
                      <tr key={row.symbol || index} className={row.symbol === activeSymbol ? "is-active" : ""}>
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

          <div className="split-2">
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
                  <div key={trade.id || index} className="timeline-row">
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

        <aside className="tv-side">
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
                  <div key={row.symbol || row.id || index} className="timeline-row" style={{ borderColor: (row.symbol || row.stock_code) === activeSymbol ? "rgba(59,130,246,0.35)" : undefined }}>
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

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Selection Summary</h2>
            </div>
            <div className="tabular-list">
              <div className="kv-row"><span className="subtle">Selected</span><span className="mono">{activeSymbol}</span></div>
              <div className="kv-row"><span className="subtle">Score</span><span className="mono">{Number(activeRank?.score || 0).toFixed(0)}</span></div>
              <div className="kv-row"><span className="subtle">20d</span><span className={Number(activeRank?.ret_20d || 0) >= 0 ? "profit mono" : "loss mono"}>{pct(activeRank?.ret_20d || 0)}</span></div>
              <div className="kv-row"><span className="subtle">Position PnL</span><span className={Number(activePosition?.pnl_pct || 0) >= 0 ? "profit mono" : "loss mono"}>{pct(activePosition?.pnl_pct || 0)}</span></div>
            </div>
          </GlassCard>
        </aside>
      </div>
    </div>
  );
}
