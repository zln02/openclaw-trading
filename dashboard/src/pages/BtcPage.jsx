import {
  Bitcoin,
  CandlestickChart,
  Newspaper,
  Radar,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  getBtcCandles,
  getBtcComposite,
  getBtcFilters,
  getBtcNews,
  getBtcPortfolio,
  getBtcTrades,
} from "../api";
import usePolling from "../hooks/usePolling";
import { compactTime, krw, pct, sparkline } from "../lib/format";
import CircularGauge from "../components/ui/CircularGauge";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
import { ErrorState, EmptyState } from "../components/ui/PageState";
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
  if (key.includes("bull")) {
    return "#22c55e";
  }
  if (key.includes("bear")) {
    return "#ef4444";
  }
  return "#6b7280";
}

export default function BtcPage() {
  const { data: composite, error: compositeError, loading: compositeLoading } = usePolling(getBtcComposite, 30000);
  const { data: portfolio, loading: portfolioLoading } = usePolling(getBtcPortfolio, 30000);
  const { data: trades } = usePolling(getBtcTrades, 60000);
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
  const scoreBars = sectionBarData(composite);
  const sentimentValue = Number(composite?.fg_value || 0);
  const tradeRows = trades?.trades || trades || [];
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

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>BTC Live Trading Desk</h1>
          <p>
            Composite score, on-chain filters, live position context, and execution trace in one dense
            operator view.
          </p>
        </div>
        <StatusBadge status={composite?.regime || composite?.trend || "TRANSITION"} />
      </div>

      {compositeError ? <ErrorState message={`BTC API connection failed: ${compositeError}`} /> : null}

      <div className="tv-terminal">
        <aside className="tv-left-rail">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Watchlist</h2>
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
                    {item.symbol === "BTC" ? krw(item.last) : typeof item.last === "number" ? Number(item.last).toLocaleString() : item.last}
                  </span>
                  <span className={Number(item.delta || 0) >= 0 ? "profit mono" : "loss mono"}>
                    {pct(item.delta || 0)}
                  </span>
                  <span className="subtle">{item.tag}</span>
                </button>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Signal Board</h2>
            </div>
            <div className="score-list">
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
          </GlassCard>
        </aside>

        <div className="tv-main tv-stack">
          <GlassCard className="card-pad" accent>
            <div className="symbol-header">
              <div>
                <div className="symbol-code">{selectedWatch === "BTC" ? "BTCKRW" : selectedWatch}</div>
                <div className="symbol-meta">
                  <span className="toolbar-chip mono">Upbit</span>
                  <span className="toolbar-chip">Spot</span>
                  <span className="toolbar-chip">5m</span>
                  <span className="toolbar-chip">Live Feed</span>
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="symbol-price">
                  {krw(Number(portfolio?.summary?.btc_price || portfolio?.summary?.current_price || candleSeries.at(-1)?.value || 0))}
                </div>
                <div className={Number(currentPosition?.pnl_pct || 0) >= 0 ? "profit" : "loss"} style={{ marginTop: 6, fontWeight: 700 }}>
                  {pct(currentPosition?.pnl_pct || 0)}
                </div>
              </div>
            </div>
            {candlesLoading ? <LoadingSkeleton height={420} /> : <LightweightPriceChart title="Price Panel" data={candleSeries} />}
          </GlassCard>

          <div className="split-2">
            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>Recent Trades</h2>
              </div>
              <div className="table-shell">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Action</th>
                      <th>Price</th>
                      <th>PnL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(tradeRows || []).slice(0, 8).map((trade, index) => (
                      <tr key={trade.id || index}>
                        <td>{compactTime(trade.created_at || trade.timestamp)}</td>
                        <td>
                          <span
                            className={`trade-badge ${
                              String(trade.action || trade.trade_type || "").toUpperCase() === "BUY"
                                ? "badge-buy"
                                : String(trade.action || trade.trade_type || "").toUpperCase() === "SELL"
                                  ? "badge-sell"
                                  : "badge-hold"
                            }`.trim()}
                          >
                            {trade.action || trade.trade_type || "HOLD"}
                          </span>
                        </td>
                        <td>{krw(trade.price || trade.entry_price)}</td>
                        <td className={Number(trade.pnl_pct || 0) >= 0 ? "profit glow-profit mono" : "loss glow-loss mono"}>
                          {pct(trade.pnl_pct || 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassCard>

            <GlassCard className="card-pad">
              <div className="panel-title">
                <h2>News Feed</h2>
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
                    <div className="subtle" style={{ fontSize: 13 }}>
                      {item.source || item.domain || "CryptoPanic"}
                    </div>
                  </div>
                ))}
                {newsRows.length === 0 ? <EmptyState message="No BTC news available." /> : null}
              </div>
            </GlassCard>
          </div>
        </div>

        <aside className="tv-side">
          <GlassCard className="card-pad" accent>
            <div className="panel-title">
              <h2>Composite Score</h2>
              <Bitcoin size={18} color="var(--text-secondary)" />
            </div>
            {compositeLoading ? (
              <LoadingSkeleton height={280} />
            ) : (
              <>
                <CircularGauge
                  value={Number(composite?.composite?.total ?? composite?.total ?? 0)}
                  label="Score"
                  subtitle="Execution signal"
                  size={190}
                />
                <div className="score-list">
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

          <GlassCard
            className={`card-pad ${currentPosition ? (Number(currentPosition.pnl_pct || 0) >= 0 ? "glass-card--profit" : "glass-card--loss") : ""}`.trim()}
          >
            <div className="panel-title">
              <h2>Position</h2>
              <ShieldCheck size={18} color="var(--text-secondary)" />
            </div>
            {portfolioLoading ? (
              <LoadingSkeleton height={220} />
            ) : currentPosition ? (
              <div className="tabular-list">
                <div className="kv-row"><span className="subtle">Entry</span><span className="mono">{krw(currentPosition.entry_price || 0)}</span></div>
                <div className="kv-row"><span className="subtle">Current</span><span className="mono">{krw(currentPosition.current_price || currentPosition.market_price || 0)}</span></div>
                <div className="kv-row"><span className="subtle">PnL</span><span className={Number(currentPosition.pnl_pct || 0) >= 0 ? "profit mono glow-profit" : "loss mono glow-loss"}>{pct(currentPosition.pnl_pct || 0)}</span></div>
                <div className="kv-row"><span className="subtle">Size</span><span className="mono">{currentPosition.quantity || currentPosition.size || "--"}</span></div>
                <div className="kv-row"><span className="subtle">Side</span><span className="mono">{currentPosition.side || currentPosition.position_side || "OPEN"}</span></div>
              </div>
            ) : (
              <EmptyState message="No active BTC position." />
            )}
          </GlassCard>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Sentiment & Filters</h2>
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
