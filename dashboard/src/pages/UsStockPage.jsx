import { DollarSign, Globe2, LineChart, Wallet2 } from "lucide-react";
import { useState } from "react";
import { getUsChart, getUsFx, getUsMarket, getUsPositions, getUsTrades } from "../api";
import usePolling from "../hooks/usePolling";
import { buildSparkline, compactTime, num, pct, usd } from "../lib/format";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import MiniSparkline from "../components/ui/MiniSparkline";
import { EmptyState } from "../components/ui/PageState";

export default function UsStockPage() {
  const { data: market, loading: marketLoading } = usePolling(getUsMarket, 60000);
  const { data: fx } = usePolling(getUsFx, 60000);
  const { data: positions, loading: positionsLoading } = usePolling(getUsPositions, 30000);
  const { data: trades } = usePolling(getUsTrades, 30000);

  const ranking = market?.top || market?.momentum || [];
  const openPositions = positions?.positions || positions?.open_positions || [];
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const activeSymbol = selectedSymbol || ranking[0]?.symbol || openPositions[0]?.symbol || "AAPL";
  const { data: chartData, loading: chartLoading } = usePolling(() => getUsChart(activeSymbol, "3mo"), 60000, [activeSymbol]);

  const chartSeries = (chartData?.candles || []).map((row) => ({
    time: row.time || row.date,
    open: Number(row.open || 0),
    high: Number(row.high || 0),
    low: Number(row.low || 0),
    close: Number(row.close || 0),
    volume: Number(row.volume || 0),
    value: Number(row.close || 0),
  }));

  const marketCards = [
    { label: "S&P 500", value: market?.sp500 ?? market?.spx ?? 0, delta: Number(market?.sp500_change_pct || 0), accent: "var(--accent-us)" },
    { label: "NASDAQ", value: market?.nasdaq ?? market?.ndx ?? 0, delta: Number(market?.nasdaq_change_pct || 0), accent: "var(--accent-us)" },
    { label: "DOW", value: market?.dji ?? market?.dow ?? 0, delta: Number(market?.dji_change_pct || 0), accent: "var(--accent-us)" },
    { label: "USD/KRW", value: fx?.rate ?? fx?.usdkrw ?? 0, delta: Number(fx?.change_pct || 0), accent: "var(--accent-btc)" },
  ];

  const actionBadgeVariant = (action) => {
    const normalized = String(action || "HOLD").toUpperCase();
    if (normalized === "BUY") return "buy";
    if (normalized === "SELL") return "sell";
    if (normalized === "SKIP") return "warning";
    return "hold";
  };

  return (
    <div className="space-y-[var(--content-gap)]">
      <div className="grid gap-[var(--content-gap)] lg:grid-cols-2 xl:grid-cols-4">
        {marketCards.map((card, index) => (
          <Card
            key={card.label}
            title={card.label}
            icon={index === 3 ? <DollarSign size={14} /> : <Globe2 size={14} />}
            delay={index}
          >
            <div className="space-y-3">
              <div className="numeric text-2xl font-semibold text-[color:var(--text-primary)]">{num(card.value, 2)}</div>
              <div className={`numeric text-sm ${Number(card.delta || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                {pct(card.delta || 0)}
              </div>
              <MiniSparkline data={buildSparkline(card.value, card.delta)} tone={card.accent} />
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-[var(--content-gap)] xl:grid-cols-2">
        <Card title="미국 모멘텀 랭킹" icon={<LineChart size={14} />} delay={4} bodyClassName="p-0">
          {marketLoading ? (
            <LoadingSkeleton height={440} className="m-4" />
          ) : (
            <div className="overflow-x-auto scrollbar-subtle px-4 pb-4">
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>심볼</th>
                    <th>5일</th>
                    <th>20일</th>
                    <th>거래량</th>
                    <th>고점 근접</th>
                    <th>점수</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.slice(0, 12).map((row, index) => (
                    <tr
                      key={row.symbol || index}
                      className={activeSymbol === row.symbol ? "data-flash" : ""}
                      onClick={() => setSelectedSymbol(row.symbol)}
                    >
                      <td>
                        <div className="font-medium">{row.symbol}</div>
                      </td>
                      <td className={`numeric ${Number(row.ret_5d || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                        {pct(row.ret_5d || 0)}
                      </td>
                      <td className={`numeric ${Number(row.ret_20d || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                        {pct(row.ret_20d || 0)}
                      </td>
                      <td className="numeric">{Number(row.volume_ratio || row.vol_ratio || 0).toFixed(2)}x</td>
                      <td className="numeric">{Number(row.near_high || row.high_proximity || 0).toFixed(1)}%</td>
                      <td className="numeric">{Number(row.score || 0).toFixed(0)}</td>
                    </tr>
                  ))}
                  {ranking.length === 0 ? (
                    <tr>
                      <td colSpan="6">
                        <EmptyState message="미국 모멘텀 랭킹 데이터가 없습니다." />
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="미국 DRY-RUN 포지션" icon={<Wallet2 size={14} />} delay={5} bodyClassName="space-y-4">
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">선택 심볼</div>
                <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">{activeSymbol}</div>
              </div>
              <Badge variant="us">미국 DRY-RUN</Badge>
            </div>
            {chartLoading ? (
              <LoadingSkeleton height={240} />
            ) : (
              <LightweightPriceChart title={`${activeSymbol} 가격`} data={chartSeries} height={240} />
            )}
          </div>

          {positionsLoading ? (
            <LoadingSkeleton height={240} />
          ) : openPositions.length === 0 ? (
            <EmptyState message="현재 미국 DRY-RUN 포지션이 없습니다." />
          ) : (
            <div className="space-y-3">
              {openPositions.slice(0, 6).map((row, index) => (
                <div key={row.symbol || row.id || index} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-[color:var(--text-primary)]">{row.symbol || row.stock_code}</div>
                      <div className="mt-1 text-xs text-[color:var(--text-muted)]">
                        수량 {row.quantity || 0} · 진입 {usd(row.entry_price || row.price)}
                      </div>
                    </div>
                    <div className={`numeric text-sm ${Number(row.pnl_pct || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                      {pct(row.pnl_pct || 0)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
              최근 실행 기록
            </div>
            <div className="space-y-2">
              {(trades || []).slice(0, 5).map((trade, index) => (
                <div key={trade.id || index} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                  <div className="flex items-center justify-between">
                    <Badge variant={actionBadgeVariant(trade.action || trade.trade_type)}>
                      {String(trade.action || trade.trade_type || "HOLD").toUpperCase()}
                    </Badge>
                    <span className="numeric text-xs text-[color:var(--text-muted)]">{compactTime(trade.timestamp || trade.created_at)}</span>
                  </div>
                  <div className="mt-2 numeric text-sm text-[color:var(--text-secondary)]">
                    {(trade.symbol || "US")} · {usd(trade.price)} · 수량 {trade.quantity || 0}
                  </div>
                </div>
              ))}
              {(trades || []).length === 0 ? <EmptyState message="미국 모의 거래 이력이 없습니다." /> : null}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
