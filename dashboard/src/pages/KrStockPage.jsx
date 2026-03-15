import { ArrowUpDown, Landmark, PieChart as PieChartIcon, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import {
  getKrTop,
  getStockChart,
  getStockMarket,
  getStockPortfolio,
  getStockStrategy,
  getStockTrades,
} from "../api";
import usePolling from "../hooks/usePolling";
import { compactTime, krw, num, pct } from "../lib/format";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState, ErrorState } from "../components/ui/PageState";
import PortfolioPieChart from "../components/ui/PortfolioPieChart";

const PIE_COLORS = ["#00d4aa", "#3b82f6", "#f7931a", "#8ea6ff", "#ffa502", "#ff6b81"];

function gradeVariant(grade) {
  const key = String(grade || "").toUpperCase();
  if (key === "A") return "profit";
  if (key === "B") return "info";
  if (key === "C") return "warning";
  if (key === "D") return "loss";
  return "neutral";
}

function resolvePositionValue(row) {
  const evaluation = Number(row?.evaluation || row?.evaluation_amount || row?.market_value || 0);
  if (evaluation > 0) {
    return evaluation;
  }
  return Number(row?.current_price || row?.price || 0) * Number(row?.quantity || row?.qty || 0);
}

export default function KrStockPage() {
  const { data: portfolio, loading: portfolioLoading, error: portfolioError } = usePolling(getStockPortfolio, 30000);
  const { data: topStocks, loading: topLoading } = usePolling(getKrTop, 60000);
  const { data: trades, loading: tradesLoading, error: tradesError } = usePolling(getStockTrades, 30000);
  const { data: market } = usePolling(getStockMarket, 60000);
  const { data: strategy } = usePolling(getStockStrategy, 60000);

  const ranking = Array.isArray(topStocks) ? topStocks : [];
  const positions = portfolio?.positions || portfolio?.open_positions || portfolio?.holdings || [];
  const [sortKey, setSortKey] = useState("score");
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const activeSymbol = selectedSymbol || ranking[0]?.stock_code || positions[0]?.stock_code || positions[0]?.code || "005930";
  const { data: chartData, loading: chartLoading } = usePolling(() => getStockChart(activeSymbol, "1d"), 60000, [activeSymbol]);

  const chartSeries = useMemo(
    () =>
      (chartData?.candles || []).map((row) => ({
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

  const totalEvaluation = positions.reduce((sum, row) => sum + resolvePositionValue(row), 0);
  const pieData = positions.map((row, index) => {
    const value = resolvePositionValue(row);
    const share = totalEvaluation > 0 ? (value / totalEvaluation) * 100 : Number(row.weight || 0);
    return {
      name: row.stock_name || row.name || row.stock_code || row.code,
      value,
      displayValue: krw(value),
      share: `${Number(share || 0).toFixed(1)}%`,
      color: PIE_COLORS[index % PIE_COLORS.length],
      subtitle: row.stock_code || row.code,
    };
  });

  const sortedRanking = [...ranking].sort((a, b) => Number(b?.[sortKey] || 0) - Number(a?.[sortKey] || 0));
  const marketCards = [
    { label: "KOSPI", value: market?.kospi ?? 0, delta: Number(market?.kospi_change_pct || 0) },
    { label: "KOSDAQ", value: market?.kosdaq ?? 0, delta: Number(market?.kosdaq_change_pct || 0) },
    { label: "S&P 500", value: num(market?.sp500 ?? 0, 2), delta: 0 },
    { label: "USD/KRW", value: num(market?.usdkrw ?? 0, 2), delta: 0 },
    { label: "BTC", value: `$${num(market?.btc ?? 0, 2)}`, delta: 0 },
    { label: "전략 신뢰도", value: `${Number(strategy?.confidence || 0).toFixed(0)}%`, delta: Number(strategy?.ml_prediction || 50) - 50 },
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
      {portfolioError && (
        <ErrorState message={`KR 포트폴리오 API 연결 실패: ${portfolioError}`} />
      )}
      {tradesError && (
        <ErrorState message={`KR 매매 내역 API 연결 실패: ${tradesError}`} />
      )}
      <div className="grid gap-[var(--content-gap)] xl:grid-cols-[1.6fr_1fr]">
        <Card title="포트폴리오 비중" icon={<PieChartIcon size={14} />} delay={0}>
          {portfolioLoading ? (
            <LoadingSkeleton height={420} />
          ) : pieData.length === 0 ? (
            <EmptyState message="현재 보유 중인 국내 포지션이 없습니다." />
          ) : (
            <div className="space-y-4">
              <PortfolioPieChart data={pieData} />
              <div className="overflow-x-auto scrollbar-subtle">
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>종목</th>
                      <th>수량</th>
                      <th>현재가</th>
                      <th>수익률</th>
                      <th>비중</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.slice(0, 10).map((row, index) => {
                      const weight = totalEvaluation > 0 ? (resolvePositionValue(row) / totalEvaluation) * 100 : Number(row.weight || 0);
                      return (
                        <tr key={row.stock_code || row.code || index}>
                          <td>
                            <div>{row.stock_name || row.name || row.stock_code || row.code}</div>
                            <div className="mt-1 text-xs text-[color:var(--text-muted)]">{row.stock_code || row.code}</div>
                          </td>
                          <td className="numeric">{num(row.quantity || row.qty || 0)}</td>
                          <td className="numeric">{krw(row.current_price || row.price)}</td>
                          <td className={`numeric ${Number(row.pnl_pct || row.return_pct || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                            {pct(row.pnl_pct || row.return_pct || 0)}
                          </td>
                          <td className="numeric">{weight.toFixed(1)}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>

        <Card title="시장 요약" icon={<Landmark size={14} />} delay={1} bodyClassName="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {marketCards.map((item) => (
              <div key={item.label} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{item.label}</div>
                <div className="mt-2 numeric text-sm text-[color:var(--text-primary)]">{typeof item.value === "string" ? item.value : num(item.value, 2)}</div>
                <div className={`mt-1 numeric text-xs ${Number(item.delta || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                  {pct(item.delta || 0)}
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">선택 종목</div>
                <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">{activeSymbol}</div>
              </div>
              <Badge variant="kr">{strategy?.mode || "국내 전략"}</Badge>
            </div>
            <div className="mb-3 rounded-lg border border-white/5 bg-[rgba(255,255,255,0.02)] px-3 py-2 text-sm text-[color:var(--text-secondary)]">
              {strategy?.summary || strategy?.market_outlook || "전략 요약이 아직 준비되지 않았습니다."}
            </div>
            {chartLoading ? (
              <LoadingSkeleton height={220} />
            ) : (
              <LightweightPriceChart title={`${activeSymbol} 가격`} data={chartSeries} height={220} />
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-[var(--content-gap)] xl:grid-cols-2">
        <Card
          title="모멘텀 랭킹"
          icon={<ArrowUpDown size={14} />}
          action={
            <div className="flex gap-1">
              {[
                ["score", "룰"],
                ["ret_5d", "5일"],
                ["ret_20d", "20일"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSortKey(key)}
                  className={`rounded-full px-2 py-1 text-[11px] ${
                    sortKey === key ? "bg-white/10 text-white" : "text-[color:var(--text-secondary)]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          }
          delay={2}
          bodyClassName="p-0"
        >
          {topLoading ? (
            <LoadingSkeleton height={420} className="m-4" />
          ) : (
            <div className="overflow-x-auto scrollbar-subtle px-4 pb-4">
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>순위</th>
                    <th>종목</th>
                    <th>5일</th>
                    <th>20일</th>
                    <th>현재가</th>
                    <th>점수</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRanking.slice(0, 10).map((row, index) => (
                    <tr
                      key={row.stock_code || index}
                      className={activeSymbol === row.stock_code ? "data-flash" : ""}
                      onClick={() => setSelectedSymbol(row.stock_code)}
                    >
                      <td className="numeric text-[color:var(--text-secondary)]">{index + 1}</td>
                      <td>
                        <div className="font-medium text-[color:var(--text-primary)]">{row.stock_name || row.stock_code}</div>
                        <div className="mt-1 text-xs text-[color:var(--text-muted)]">{row.stock_code}</div>
                      </td>
                      <td className={`numeric ${Number(row.ret_5d || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                        {pct(row.ret_5d || 0)}
                      </td>
                      <td className={`numeric ${Number(row.ret_20d || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                        {pct(row.ret_20d || 0)}
                      </td>
                      <td className="numeric">{krw(row.current_price || 0)}</td>
                      <td>
                        <Badge variant={gradeVariant(row.grade || (Number(row.score || 0) >= 80 ? "A" : Number(row.score || 0) >= 60 ? "B" : Number(row.score || 0) >= 40 ? "C" : "D"))}>
                          {num(row.score || row.rule_score || 0)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                  {sortedRanking.length === 0 ? (
                    <tr>
                      <td colSpan="6">
                        <EmptyState message="국내 모멘텀 랭킹 데이터가 없습니다." />
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="거래 기록" icon={<Wallet size={14} />} delay={3} bodyClassName="p-0">
          {tradesLoading ? (
            <LoadingSkeleton height={420} className="m-4" />
          ) : (
            <div className="overflow-x-auto scrollbar-subtle px-4 pb-4">
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>시각</th>
                    <th>종목</th>
                    <th>액션</th>
                    <th>가격</th>
                    <th>손익</th>
                  </tr>
                </thead>
                <tbody>
                  {(trades || []).slice(0, 12).map((trade, index) => {
                    const action = String(trade.trade_type || trade.action || "").toUpperCase();
                    return (
                      <tr key={trade.trade_id || index}>
                        <td className="numeric text-[color:var(--text-secondary)]">{compactTime(trade.created_at)}</td>
                        <td>
                          <div>{trade.stock_name || trade.stock_code}</div>
                        </td>
                        <td>
                          <Badge variant={actionBadgeVariant(action)}>{action || "HOLD"}</Badge>
                        </td>
                        <td className="numeric">{krw(trade.price)}</td>
                        <td className={`numeric ${Number(trade.pnl_pct || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                          {pct(trade.pnl_pct || 0)}
                        </td>
                      </tr>
                    );
                  })}
                  {(trades || []).length === 0 ? (
                    <tr>
                      <td colSpan="5">
                        <EmptyState message="국내 거래 이력이 없습니다." />
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
