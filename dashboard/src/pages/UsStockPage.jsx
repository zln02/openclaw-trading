import { DollarSign, Globe2, LineChart, Search, TrendingUp, Wallet2, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { getUsChart, getUsFx, getUsMarket, getUsTrades } from "../api";
import usePolling from "../hooks/usePolling";
import { usePortfolio } from "../context/PortfolioContext";
import { buildSparkline, compactTime, krw, num, pct, usd } from "../lib/format";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import LightweightPriceChart from "../components/ui/LightweightPriceChart";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import MiniSparkline from "../components/ui/MiniSparkline";
import { EmptyState, ErrorState } from "../components/ui/PageState";
import { UsStrategyPanel } from "../components/StrategyPanel";

const US_TIMEFRAMES = [
  { label: "5일",  period: "5d",  interval: "1h",  pollMs: 60000  },
  { label: "1개월", period: "1mo", interval: "1d",  pollMs: 120000 },
  { label: "3개월", period: "3mo", interval: "1d",  pollMs: 120000 },
  { label: "6개월", period: "6mo", interval: "1d",  pollMs: 300000 },
  { label: "1년",   period: "1y",  interval: "1d",  pollMs: 300000 },
  { label: "5년",   period: "5y",  interval: "1wk", pollMs: 300000 },
];

function UsAccountBanner({ positions, fx, loading }) {
  if (loading) return <LoadingSkeleton height={80} />;
  const usdKrw = Number(fx?.rate || fx?.usdkrw || 1350);
  const s = positions?.summary || {};
  const totalInvested = Number(s.total_invested || 0);
  const totalCurrent = Number(s.total_current || 0);
  const pnlUsd = Number(s.total_pnl_usd || (totalCurrent - totalInvested) || 0);
  const pnlPct = Number(s.total_pnl_pct || 0);
  const pnlKrw = pnlUsd * usdKrw;
  const count = Number(s.count || 0);

  if (!totalCurrent && !totalInvested) return null;

  const cells = [
    { label: "총 투자금",          value: usd(totalInvested), delta: null },
    { label: "총 평가금",          value: usd(totalCurrent),  delta: null },
    { label: "미실현 손익 ($)",    value: `${pnlUsd >= 0 ? "+" : ""}${usd(pnlUsd)}`, delta: pnlPct, emphasize: true },
    { label: "미실현 손익 (₩)",    value: krw(pnlKrw),        delta: pnlPct, emphasize: true },
    { label: "보유 종목 / 환율",   value: `${count}개`,        delta: null, sub: `1$ = ${Number(usdKrw).toLocaleString()}₩` },
  ];

  return (
    <div className="rounded-[var(--panel-radius)] border border-white/10 bg-[color:var(--bg-panel)] px-4 py-3 shadow-[var(--shadow-panel)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
          US 계좌 현황 (DRY-RUN)
        </span>
        <Badge variant={pnlPct >= 0 ? "profit" : "loss"}>
          {pnlPct >= 0 ? "+" : ""}{Number(pnlPct).toFixed(2)}%
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
            {cell.sub && <div className="mt-0.5 text-[11px] text-[color:var(--text-muted)]">{cell.sub}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function SymbolSearch({ searchList, activeSymbol, onSelect }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);

  const filtered = query.trim()
    ? searchList.filter((s) => s.symbol?.toUpperCase().includes(query.toUpperCase()) || s.name?.toLowerCase().includes(query.toLowerCase()))
    : searchList.slice(0, 10);

  function select(symbol) {
    onSelect(symbol);
    setQuery("");
    setOpen(false);
  }

  return (
    <div className="relative">
      <div
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-1.5 cursor-text min-w-[140px]"
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
              if (e.key === "Enter" && filtered[0]) select(filtered[0].symbol);
              if (e.key === "Escape") { setQuery(""); setOpen(false); }
            }}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            placeholder="심볼 / 종목명"
            className="w-full bg-transparent text-xs text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] outline-none uppercase"
          />
        ) : (
          <span className="text-xs font-semibold text-[color:var(--text-primary)]">{activeSymbol}</span>
        )}
        {open && query && (
          <button type="button" onClick={(e) => { e.stopPropagation(); setQuery(""); }}>
            <X size={11} className="text-[color:var(--text-muted)]" />
          </button>
        )}
      </div>

      {open && filtered.length > 0 && (
        <div className="absolute top-full left-0 z-50 mt-1 w-56 rounded-xl border border-white/10 bg-[rgba(18,18,26,0.97)] shadow-xl backdrop-blur-xl overflow-hidden">
          {filtered.map((s) => (
            <button
              key={s.symbol}
              type="button"
              onMouseDown={() => select(s.symbol)}
              className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-white/[0.06] transition-colors ${
                s.symbol === activeSymbol ? "bg-white/[0.05]" : ""
              }`}
            >
              <span className="text-xs font-semibold text-[color:var(--text-primary)]">{s.symbol}</span>
              <Badge variant={s.source === "보유" ? "profit" : "neutral"} className="text-[10px]">
                {s.source}
              </Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function UsStockPage() {
  const [tfIndex, setTfIndex] = useState(2); // 기본 3개월
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const tf = US_TIMEFRAMES[tfIndex];

  const { data: market, loading: marketLoading, error: marketError } = usePolling(getUsMarket, 60000);
  const { data: fx } = usePolling(getUsFx, 60000);
  const { usPortfolio: positions, errors: portfolioErrors } = usePortfolio();
  const positionsLoading = positions === null && !portfolioErrors?.us;
  const positionsError = portfolioErrors?.us || null;
  const { data: trades, error: tradesError } = usePolling(getUsTrades, 30000);

  const ranking = market?.top || market?.momentum || [];
  const openPositions = positions?.positions || positions?.open_positions || [];
  const activeSymbol = selectedSymbol || ranking[0]?.symbol || openPositions[0]?.symbol || "AAPL";

  const { data: chartData, loading: chartLoading, error: chartError } = usePolling(
    () => getUsChart(activeSymbol, tf.period, tf.interval),
    tf.pollMs,
    [activeSymbol, tf.period, tf.interval],
  );

  const searchList = useMemo(() => {
    const map = new Map();
    openPositions.forEach((p) => map.set(p.symbol, { symbol: p.symbol, source: "보유" }));
    ranking.forEach((r) => { if (!map.has(r.symbol)) map.set(r.symbol, { symbol: r.symbol, source: "랭킹" }); });
    return Array.from(map.values());
  }, [openPositions, ranking]);

  const chartSeries = useMemo(
    () =>
      (chartData?.candles || []).map((row) => ({
        time: row.time || row.date,
        open: Number(row.open || 0),
        high: Number(row.high || 0),
        low: Number(row.low || 0),
        close: Number(row.close || 0),
        volume: Number(row.volume || 0),
        value: Number(row.close || 0),
      })),
    [chartData],
  );

  const marketCards = [
    { label: "S&P 500", value: market?.sp500 ?? market?.spx ?? 0,  delta: Number(market?.sp500_change_pct  || 0), accent: "var(--accent-us)"  },
    { label: "NASDAQ",  value: market?.nasdaq ?? market?.ndx ?? 0, delta: Number(market?.nasdaq_change_pct || 0), accent: "var(--accent-us)"  },
    { label: "DOW",     value: market?.dji ?? market?.dow ?? 0,    delta: Number(market?.dji_change_pct    || 0), accent: "var(--accent-us)"  },
    { label: "USD/KRW", value: fx?.rate ?? fx?.usdkrw ?? 0,        delta: Number(fx?.change_pct            || 0), accent: "var(--accent-btc)" },
  ];

  const actionBadgeVariant = (action) => {
    const normalized = String(action || "HOLD").toUpperCase();
    if (normalized === "BUY")  return "buy";
    if (normalized === "SELL") return "sell";
    if (normalized === "SKIP") return "warning";
    return "hold";
  };

  return (
    <div className="space-y-[var(--content-gap)]">
      <UsAccountBanner positions={positions} fx={fx} loading={positionsLoading} />

      {marketError   && <ErrorState message={`US 시장 데이터 API 연결 실패: ${marketError}`} />}
      {positionsError && <ErrorState message={`US 포지션 API 연결 실패: ${positionsError}`} />}

      {/* ── 시장 지수 카드 ── */}
      <div className="grid gap-[var(--content-gap)] lg:grid-cols-2 xl:grid-cols-4">
        {marketCards.map((card, index) => (
          <Card key={card.label} title={card.label} icon={index === 3 ? <DollarSign size={14} /> : <Globe2 size={14} />} delay={index}>
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

      {/* ── 메인 차트 ── */}
      <Card
        title={`${activeSymbol} 가격`}
        icon={<TrendingUp size={14} />}
        delay={4}
        bodyClassName="space-y-3"
        action={
          <div className="flex items-center gap-2">
            <SymbolSearch searchList={searchList} activeSymbol={activeSymbol} onSelect={setSelectedSymbol} />
            <div className="flex gap-0.5">
              {US_TIMEFRAMES.map((t, i) => (
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
          <LoadingSkeleton height={400} />
        ) : chartError ? (
          <ErrorState message={`차트 데이터 로딩 실패: ${chartError}`} />
        ) : (
          <LightweightPriceChart title={`${activeSymbol} · ${tf.label}`} data={chartSeries} height={400} />
        )}
      </Card>

      {/* ── 랭킹 + 포지션 / 거래 ── */}
      <div className="grid gap-[var(--content-gap)] xl:grid-cols-2">
        <Card title="미국 모멘텀 랭킹" icon={<LineChart size={14} />} delay={5} bodyClassName="p-0">
          {marketLoading ? (
            <LoadingSkeleton height={400} className="m-4" />
          ) : (
            <div className="overflow-x-auto scrollbar-subtle px-4 pb-4">
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>심볼</th><th>5일</th><th>20일</th><th>거래량</th><th>고점 근접</th><th>점수</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.slice(0, 12).map((row, index) => (
                    <tr
                      key={row.symbol || index}
                      className={`cursor-pointer ${activeSymbol === row.symbol ? "data-flash" : ""}`}
                      onClick={() => setSelectedSymbol(row.symbol)}
                    >
                      <td><div className="font-medium">{row.symbol}</div></td>
                      <td className={`numeric ${Number(row.ret_5d  || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>{pct(row.ret_5d  || 0)}</td>
                      <td className={`numeric ${Number(row.ret_20d || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>{pct(row.ret_20d || 0)}</td>
                      <td className="numeric">{Number(row.volume_ratio || row.vol_ratio || 0).toFixed(2)}x</td>
                      <td className="numeric">{Number(row.near_high  || row.high_proximity || 0).toFixed(1)}%</td>
                      <td className="numeric">{Number(row.score     || 0).toFixed(0)}</td>
                    </tr>
                  ))}
                  {ranking.length === 0 && (
                    <tr><td colSpan="6"><EmptyState message="미국 모멘텀 랭킹 데이터가 없습니다." /></td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="미국 DRY-RUN 포지션" icon={<Wallet2 size={14} />} delay={6} bodyClassName="space-y-4">
          {positionsLoading ? (
            <LoadingSkeleton height={200} />
          ) : openPositions.length === 0 ? (
            <EmptyState message="US 보유 종목이 없습니다" />
          ) : (
            <div className="overflow-x-auto scrollbar-subtle">
              <table className="terminal-table">
                <thead>
                  <tr><th>심볼</th><th>수량</th><th>진입가</th><th>현재가</th><th>손익($)</th><th>수익률</th></tr>
                </thead>
                <tbody>
                  {openPositions.slice(0, 8).map((row, index) => {
                    const pnlPct = Number(row.pnl_pct || 0);
                    const pnlUsd = Number(row.pnl_usd || 0);
                    return (
                      <tr
                        key={row.symbol || row.id || index}
                        className={`cursor-pointer ${activeSymbol === row.symbol ? "data-flash" : ""}`}
                        onClick={() => setSelectedSymbol(row.symbol)}
                      >
                        <td className="font-medium text-[color:var(--text-primary)]">{row.symbol || row.stock_code}</td>
                        <td className="numeric">{row.quantity || 0}</td>
                        <td className="numeric text-[color:var(--text-secondary)]">{usd(row.entry_price || row.price)}</td>
                        <td className="numeric">{usd(row.current_price || row.entry_price || row.price)}</td>
                        <td className={`numeric ${pnlUsd >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                          {pnlUsd !== 0 ? `${pnlUsd >= 0 ? "+" : ""}${usd(pnlUsd)}` : "—"}
                        </td>
                        <td className={`numeric ${pnlPct >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]"}`}>
                          {pct(pnlPct)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">최근 실행 기록</div>
            <div className="space-y-2">
              {(trades || []).slice(0, 4).map((trade, index) => (
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
              {tradesError ? <ErrorState message={`US 거래 로딩 실패: ${tradesError}`} /> : null}
              {(trades || []).length === 0 && !tradesError && <EmptyState message="최근 US 거래가 없습니다" />}
            </div>
          </div>
        </Card>
      </div>

      <UsStrategyPanel market={market} positions={positions} loading={positionsLoading} />
    </div>
  );
}
