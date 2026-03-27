import { ArrowUpDown, Landmark, PieChart as PieChartIcon, Search, Wallet, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import {
  getKrTop,
  getKrTrades,
  getStockChart,
  getStockMarket,
  getStockStrategy,
} from "../api";
import usePolling from "../hooks/usePolling";
import { usePortfolio } from "../context/PortfolioContext";
import { compactTime, krw, num, pct } from "../lib/format";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState, ErrorState } from "../components/ui/PageState";
import PortfolioPieChart from "../components/ui/PortfolioPieChart";
import { KrStrategyPanel } from "../components/StrategyPanel";

const PIE_COLORS = ["#00d4aa", "#3b82f6", "#f7931a", "#8ea6ff", "#ffa502", "#ff6b81"];

const KR_TIMEFRAMES = [
  { label: "5분",  interval: "5m",  limit: 200, pollMs: 60000  },
  { label: "1시간", interval: "1h",  limit: 200, pollMs: 60000  },
  { label: "1개월", interval: "1d",  limit: 22,  pollMs: 120000 },
  { label: "3개월", interval: "1d",  limit: 65,  pollMs: 120000 },
  { label: "6개월", interval: "1d",  limit: 130, pollMs: 300000 },
  { label: "1년",   interval: "1d",  limit: 250, pollMs: 300000 },
];

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
  if (evaluation > 0) return evaluation;
  return Number(row?.current_price || row?.price || 0) * Number(row?.quantity || row?.qty || 0);
}

function AccountBanner({ account, loading }) {
  if (loading) return <LoadingSkeleton height={80} />;
  if (!account) return null;

  const deposit = Number(account.deposit || 0);
  const totalEval = Number(account.total_evaluation || 0);
  const totalPurchase = Number(account.total_purchase || 0);
  const unrealizedPnl = totalEval - totalPurchase;
  const unrealizedPct = totalPurchase > 0 ? (unrealizedPnl / totalPurchase) * 100 : 0;
  const cumPct = Number(account.cumulative_pnl_pct || unrealizedPct || 0);
  const totalAsset = deposit + totalEval;

  const cells = [
    { label: "예수금",     value: krw(deposit),          delta: null },
    { label: "주식 평가",  value: krw(totalEval),         delta: null },
    { label: "총 매수금",  value: krw(totalPurchase),     delta: null },
    { label: "미실현 손익", value: krw(unrealizedPnl),    delta: unrealizedPct, emphasize: true },
    { label: "총 자산",    value: krw(totalAsset),        delta: cumPct,        emphasize: true },
  ];

  return (
    <div className="rounded-[var(--panel-radius)] border border-white/10 bg-[color:var(--bg-panel)] px-4 py-3 shadow-[var(--shadow-panel)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
          KR 계좌 현황 (모의투자)
        </span>
        <Badge variant={cumPct >= 0 ? "profit" : "loss"}>
          {cumPct >= 0 ? "+" : ""}{Number(cumPct).toFixed(2)}%
        </Badge>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {cells.map((cell) => (
          <div key={cell.label} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">{cell.label}</div>
            <div
              className={`mt-1 numeric text-sm font-semibold ${
                cell.delta != null
                  ? cell.delta >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"
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
          </div>
        ))}
      </div>
    </div>
  );
}

function StockSearch({ searchList, activeSymbol, onSelect }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);

  const filtered = query.trim()
    ? searchList.filter((s) => s.name?.includes(query) || s.code?.includes(query))
    : searchList.slice(0, 10);

  const activeInfo = searchList.find((s) => s.code === activeSymbol);

  function select(code) {
    onSelect(code);
    setQuery("");
    setOpen(false);
  }

  return (
    <div className="relative">
      <div
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-1.5 cursor-text min-w-[160px]"
        onClick={() => { setOpen(true); inputRef.current?.focus(); }}
      >
        <Search size={12} className="shrink-0 text-[color:var(--text-muted)]" />
        {open ? (
          <input
            ref={inputRef}
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && filtered[0]) select(filtered[0].code);
              if (e.key === "Escape") { setQuery(""); setOpen(false); }
            }}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            placeholder="종목명 / 코드"
            className="w-full bg-transparent text-xs text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] outline-none"
          />
        ) : (
          <span className="text-xs text-[color:var(--text-primary)] truncate max-w-[120px]">
            {activeInfo ? `${activeInfo.name} (${activeInfo.code})` : activeSymbol}
          </span>
        )}
        {open && query && (
          <button type="button" onClick={(e) => { e.stopPropagation(); setQuery(""); }}>
            <X size={11} className="text-[color:var(--text-muted)]" />
          </button>
        )}
      </div>

      {open && filtered.length > 0 && (
        <div className="absolute top-full left-0 z-50 mt-1 w-64 rounded-xl border border-white/10 bg-[rgba(18,18,26,0.97)] shadow-xl backdrop-blur-xl overflow-hidden">
          {filtered.map((s) => (
            <button
              key={s.code}
              type="button"
              onMouseDown={() => select(s.code)}
              className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-white/[0.06] transition-colors ${
                s.code === activeSymbol ? "bg-white/[0.05]" : ""
              }`}
            >
              <div className="min-w-0">
                <div className="text-xs font-medium text-[color:var(--text-primary)] truncate">{s.name}</div>
                <div className="text-[10px] text-[color:var(--text-muted)]">{s.code}</div>
              </div>
              <Badge variant={s.source === "보유" ? "profit" : "neutral"} className="shrink-0 text-[10px]">
                {s.source}
              </Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function KrStockPage() {
  const [tfIndex, setTfIndex] = useState(3); // 기본 3개월
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [sortKey, setSortKey] = useState("score");
  const tf = KR_TIMEFRAMES[tfIndex];

  const { krPortfolio: account, errors: portfolioErrors } = usePortfolio();
  const accountLoading = account === null && !portfolioErrors?.kr;
  const accountError = portfolioErrors?.kr || null;
  const { data: topStocks, loading: topLoading } = usePolling(getKrTop, 60000);
  const { data: trades, loading: tradesLoading, error: tradesError } = usePolling(getKrTrades, 30000);
  const { data: market } = usePolling(getStockMarket, 60000);
  const { data: strategy } = usePolling(getStockStrategy, 60000);

  const positions = account?.positions || [];
  const ranking = Array.isArray(topStocks) ? topStocks : [];
  const activeSymbol = selectedSymbol || ranking[0]?.stock_code || positions[0]?.code || "005930";

  const { data: chartData, loading: chartLoading, error: chartError } = usePolling(
    () => getStockChart(activeSymbol, tf.interval, tf.limit),
    tf.pollMs,
    [activeSymbol, tf.interval, tf.limit],
  );

  const searchList = useMemo(() => {
    const map = new Map();
    positions.forEach((p) => {
      const code = p.code || p.stock_code;
      map.set(code, { code, name: p.name || p.stock_name || code, source: "보유" });
    });
    ranking.forEach((r) => {
      if (!map.has(r.stock_code))
        map.set(r.stock_code, { code: r.stock_code, name: r.stock_name || r.stock_code, source: "랭킹" });
    });
    return Array.from(map.values());
  }, [positions, ranking]);

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
    { label: "KOSPI",    value: market?.kospi  ?? 0,    delta: Number(market?.kospi_change_pct  || 0) },
    { label: "KOSDAQ",   value: market?.kosdaq ?? 0,    delta: Number(market?.kosdaq_change_pct || 0) },
    { label: "S&P 500",  value: num(market?.sp500 ?? 0, 2), delta: 0 },
    { label: "USD/KRW",  value: num(market?.usdkrw ?? 0, 2), delta: 0 },
    { label: "BTC",      value: `$${num(market?.btc ?? 0, 0)}`, delta: 0 },
    { label: "전략 신뢰도", value: `${Number(strategy?.confidence || 0).toFixed(0)}%`, delta: Number(strategy?.ml_prediction || 50) - 50 },
  ];

  const actionBadgeVariant = (action) => {
    const normalized = String(action || "HOLD").toUpperCase();
    if (normalized === "BUY") return "buy";
    if (normalized === "SELL") return "sell";
    if (normalized === "SKIP") return "warning";
    return "hold";
  };

  const activeInfo = searchList.find((s) => s.code === activeSymbol);

  return (
    <div className="space-y-[var(--content-gap)]">
      <AccountBanner account={account} loading={accountLoading} />

      {accountError && <ErrorState message={`KR 계좌 API 연결 실패: ${accountError}`} />}
      {tradesError  && <ErrorState message={`KR 매매 내역 API 연결 실패: ${tradesError}`} />}

      {/* ── 메인 차트 ── */}
      <Card
        title={activeInfo ? `${activeInfo.name} (${activeInfo.code})` : activeSymbol}
        icon={<Landmark size={14} />}
        delay={0}
        bodyClassName="space-y-3"
        action={
          <div className="flex items-center gap-2">
            <StockSearch searchList={searchList} activeSymbol={activeSymbol} onSelect={setSelectedSymbol} />
            <div className="flex gap-0.5">
              {KR_TIMEFRAMES.map((t, i) => (
                <button
                  key={t.label}
                  type="button"
                  onClick={() => setTfIndex(i)}
                  className={`rounded-full px-2 py-1 text-[11px] transition-colors ${
                    tfIndex === i ? "bg-white/10 text-white font-medium" : "text-[color:var(--text-secondary)] hover:text-white"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        }
      >
        {chartLoading ? (
          <LoadingSkeleton height={420} />
        ) : chartError ? (
          <ErrorState message={`차트 데이터 로딩 실패: ${chartError}`} />
        ) : (
          <LightweightPriceChart title={`${activeSymbol} · ${tf.label}`} data={chartSeries} height={420} />
        )}
      </Card>

      {/* ── 포트폴리오 비중 + 시장 요약 ── */}
      <div className="grid gap-[var(--content-gap)] xl:grid-cols-[1.6fr_1fr]">
        <Card title="포트폴리오 비중" icon={<PieChartIcon size={14} />} delay={1}>
          {accountLoading ? (
            <LoadingSkeleton height={380} />
          ) : pieData.length === 0 ? (
            <EmptyState message="보유 종목이 없습니다" />
          ) : (
            <div className="space-y-4">
              <PortfolioPieChart data={pieData} />
              <div className="overflow-x-auto scrollbar-subtle">
                <table className="terminal-table">
                  <thead>
                    <tr>
                      <th>종목</th>
                      <th>수량</th>
                      <th>평균단가</th>
                      <th>현재가</th>
                      <th>손익금액</th>
                      <th>수익률</th>
                      <th>비중</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.slice(0, 10).map((row, index) => {
                      const weight = totalEvaluation > 0 ? (resolvePositionValue(row) / totalEvaluation) * 100 : Number(row.weight || 0);
                      const pnlPct    = Number(row.pnl_pct    || row.return_pct || 0);
                      const pnlAmount = Number(row.pnl_amount || row.pnl_krw   || 0);
                      const avgEntry  = Number(row.avg_entry  || row.price     || row.entry_price || 0);
                      const code = row.code || row.stock_code;
                      return (
                        <tr
                          key={code || index}
                          className={`cursor-pointer ${activeSymbol === code ? "data-flash" : ""}`}
                          onClick={() => setSelectedSymbol(code)}
                        >
                          <td>
                            <div>{row.name || row.stock_name || code}</div>
                            <div className="mt-1 text-xs text-[color:var(--text-muted)]">{code}</div>
                          </td>
                          <td className="numeric">{num(row.quantity || row.qty || 0)}</td>
                          <td className="numeric text-[color:var(--text-secondary)]">{avgEntry > 0 ? krw(avgEntry) : "—"}</td>
                          <td className="numeric">{krw(row.current_price || row.price)}</td>
                          <td className={`numeric ${pnlAmount >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                            {pnlAmount !== 0 ? krw(pnlAmount) : "—"}
                          </td>
                          <td className={`numeric ${pnlPct >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                            {pct(pnlPct)}
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

        <div className="space-y-[var(--content-gap)]">
          <Card title="시장 요약" icon={<Landmark size={14} />} delay={2}>
            <div className="grid grid-cols-2 gap-2">
              {marketCards.map((item) => (
                <div key={item.label} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{item.label}</div>
                  <div className="mt-2 numeric text-sm text-[color:var(--text-primary)]">
                    {typeof item.value === "string" ? item.value : num(item.value, 2)}
                  </div>
                  <div className={`mt-1 numeric text-xs ${Number(item.delta || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                    {pct(item.delta || 0)}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <KrStrategyPanel strategy={strategy} account={account} loading={accountLoading} />
        </div>
      </div>

      {/* ── 랭킹 + 거래 기록 ── */}
      <div className="grid gap-[var(--content-gap)] xl:grid-cols-2">
        <Card
          title="모멘텀 랭킹"
          icon={<ArrowUpDown size={14} />}
          action={
            <div className="flex gap-1">
              {[["score", "룰"], ["ret_5d", "5일"], ["ret_20d", "20일"]].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSortKey(key)}
                  className={`rounded-full px-2 py-1 text-[11px] ${sortKey === key ? "bg-white/10 text-white" : "text-[color:var(--text-secondary)]"}`}
                >
                  {label}
                </button>
              ))}
            </div>
          }
          delay={3}
          bodyClassName="p-0"
        >
          {topLoading ? (
            <LoadingSkeleton height={380} className="m-4" />
          ) : (
            <div className="overflow-x-auto scrollbar-subtle px-4 pb-4">
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>순위</th><th>종목</th><th>5일</th><th>20일</th><th>현재가</th><th>점수</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRanking.slice(0, 12).map((row, index) => (
                    <tr
                      key={row.stock_code || index}
                      className={`cursor-pointer ${activeSymbol === row.stock_code ? "data-flash" : ""}`}
                      onClick={() => setSelectedSymbol(row.stock_code)}
                    >
                      <td className="numeric text-[color:var(--text-secondary)]">{index + 1}</td>
                      <td>
                        <div className="font-medium text-[color:var(--text-primary)]">{row.stock_name || row.stock_code}</div>
                        <div className="mt-1 text-xs text-[color:var(--text-muted)]">{row.stock_code}</div>
                      </td>
                      <td className={`numeric ${Number(row.ret_5d  || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>{pct(row.ret_5d  || 0)}</td>
                      <td className={`numeric ${Number(row.ret_20d || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>{pct(row.ret_20d || 0)}</td>
                      <td className="numeric">{krw(row.current_price || 0)}</td>
                      <td>
                        <Badge variant={gradeVariant(row.grade || (Number(row.score || 0) >= 80 ? "A" : Number(row.score || 0) >= 60 ? "B" : Number(row.score || 0) >= 40 ? "C" : "D"))}>
                          {num(row.score || row.rule_score || 0)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                  {sortedRanking.length === 0 && (
                    <tr><td colSpan="6"><EmptyState message="국내 모멘텀 랭킹 데이터가 없습니다." /></td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="거래 기록" icon={<Wallet size={14} />} delay={4} bodyClassName="p-0">
          {tradesLoading ? (
            <LoadingSkeleton height={380} className="m-4" />
          ) : (
            <div className="overflow-x-auto scrollbar-subtle px-4 pb-4">
              <table className="terminal-table">
                <thead>
                  <tr><th>시각</th><th>종목</th><th>액션</th><th>가격</th><th>손익</th></tr>
                </thead>
                <tbody>
                  {(trades || []).slice(0, 12).map((trade, index) => {
                    const action = String(trade.trade_type || trade.action || "").toUpperCase();
                    const pnlPct = Number(trade.pnl_pct    || 0);
                    const pnlKrw = Number(trade.pnl_krw    || trade.pnl_amount || 0);
                    return (
                      <tr key={trade.trade_id || index}>
                        <td className="numeric text-[color:var(--text-secondary)]">{compactTime(trade.created_at)}</td>
                        <td><div>{trade.stock_name || trade.stock_code}</div></td>
                        <td><Badge variant={actionBadgeVariant(action)}>{action || "HOLD"}</Badge></td>
                        <td className="numeric">{krw(trade.price)}</td>
                        <td className={`numeric ${pnlPct >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                          {pnlKrw !== 0 ? krw(pnlKrw) : pct(pnlPct)}
                        </td>
                      </tr>
                    );
                  })}
                  {(trades || []).length === 0 && (
                    <tr><td colSpan="5"><EmptyState message="오늘 거래 내역이 없습니다" /></td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
