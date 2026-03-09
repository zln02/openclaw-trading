import {
  Activity,
  BadgePercent,
  Bitcoin,
  CandlestickChart,
  Clock3,
  Newspaper,
  Radar,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { useMemo } from "react";
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

      <div className="page-grid">
        <div className="col-7">
          {candlesLoading ? (
            <LoadingSkeleton height={420} />
          ) : (
            <LightweightPriceChart title="BTC Candlestick Proxy" data={candleSeries} />
          )}
        </div>

        <div className="col-5 stack">
          <GlassCard className="card-pad">
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
                  subtitle="0 to 100 gradient gauge"
                  size={220}
                />
                <div className="stack" style={{ gap: 10 }}>
                  {scoreBars.map((bar) => (
                    <div key={bar.name}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: 6,
                          fontSize: 13,
                        }}
                      >
                        <span className="subtle">{bar.name}</span>
                        <span className="mono">{bar.value}</span>
                      </div>
                      <div
                        style={{
                          height: 10,
                          borderRadius: 999,
                          background: "rgba(255,255,255,0.06)",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(Math.max(bar.value, 0), 100)}%`,
                            height: "100%",
                            background: "var(--gradient-main)",
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </GlassCard>
        </div>

        <div className="col-6">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Open Position</h2>
              <ShieldCheck size={18} color="var(--text-secondary)" />
            </div>
            {portfolioLoading ? (
              <LoadingSkeleton height={220} />
            ) : currentPosition ? (
              <div className="grid-2">
                <StatCard
                  label="Entry Price"
                  value={Number(currentPosition.entry_price || 0)}
                  prefix="₩"
                  icon={<BadgePercent size={18} />}
                  trend={sparkline([currentPosition.entry_price, currentPosition.current_price])}
                  delta={Number(currentPosition.pnl_pct || 0)}
                  tone={Number(currentPosition.pnl_pct || 0) >= 0 ? "profit" : "loss"}
                />
                <StatCard
                  label="Current Price"
                  value={Number(currentPosition.current_price || currentPosition.market_price || 0)}
                  prefix="₩"
                  icon={<TrendingUp size={18} />}
                  trend={sparkline([currentPosition.entry_price, currentPosition.current_price])}
                  delta={Number(currentPosition.pnl_pct || 0)}
                  tone={Number(currentPosition.pnl_pct || 0) >= 0 ? "profit" : "loss"}
                />
                <StatCard
                  label="PnL"
                  value={Number(currentPosition.pnl_pct || 0)}
                  suffix="%"
                  icon={<Activity size={18} />}
                  trend={sparkline([currentPosition.pnl_pct || 0, currentPosition.pnl_pct || 0])}
                  delta={Number(currentPosition.pnl_pct || 0)}
                  tone={Number(currentPosition.pnl_pct || 0) >= 0 ? "profit" : "loss"}
                />
                <StatCard
                  label="Holding Time"
                  value={0}
                  suffix="h"
                  icon={<Clock3 size={18} />}
                  trend={sparkline([1, 2, 3, 4])}
                  delta={0}
                  tone="neutral"
                />
              </div>
            ) : (
              <EmptyState message="No active BTC position." />
            )}
          </GlassCard>
        </div>

        <div className="col-6">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Fear & Greed Gauge</h2>
              <Radar size={18} color="var(--text-secondary)" />
            </div>
            <CircularGauge value={sentimentValue} label="F&G" subtitle={composite?.fg_label || "Sentiment"} size={220} />
          </GlassCard>
        </div>

        <div className="col-6">
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
                  {(tradeRows || []).slice(0, 5).map((trade, index) => (
                    <tr key={trade.id || index}>
                      <td>{compactTime(trade.created_at || trade.timestamp)}</td>
                      <td className={String(trade.action || trade.trade_type).toUpperCase() === "BUY" ? "profit" : "loss"}>
                        {trade.action || trade.trade_type || "—"}
                      </td>
                      <td>{krw(trade.price || trade.entry_price)}</td>
                      <td className={Number(trade.pnl_pct || 0) >= 0 ? "profit" : "loss"}>
                        {pct(trade.pnl_pct || 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </div>

        <div className="col-6">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>News Feed</h2>
              <Newspaper size={18} color="var(--text-secondary)" />
            </div>
            <div className="stack" style={{ gap: 12 }}>
              {newsRows.slice(0, 5).map((item, index) => (
                <div
                  key={item.id || item.url || index}
                  style={{
                    padding: 14,
                    borderRadius: 16,
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.05)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
                    <strong style={{ fontSize: 14 }}>{item.title || item.headline || "Untitled headline"}</strong>
                    <span className="pill">{item.sentiment || "Neutral"}</span>
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

        <div className="col-12">
          <div className="grid-4">
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
        </div>
      </div>
    </div>
  );
}
