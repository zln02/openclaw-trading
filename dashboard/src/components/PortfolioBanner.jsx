import PropTypes from "prop-types";
import usePolling from "../hooks/usePolling";
import { getBtcPortfolio, getStockPortfolio, getUsPositions } from "../api";

const fmtKrw = (n) => n != null ? `₩${Number(Math.round(n)).toLocaleString()}` : "₩—";
const fmtUsd = (n) => n != null ? `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "$—";
const fmtPct = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : null;

function PnlSpan({ val, pct, isKrw = true }) {
  if (val == null) return <span className="text-text-secondary text-xs">—</span>;
  const pos = val >= 0;
  const cls = pos ? "text-profit" : "text-loss";
  const formatted = isKrw ? fmtKrw(val) : `$${Math.abs(val).toFixed(0)}`;
  const sign = val >= 0 ? "+" : "−";
  const pctStr = fmtPct(pct);
  return (
    <span className={`font-mono text-xs ${cls}`}>
      {sign}{isKrw ? formatted.slice(1) : `$${Math.abs(val).toFixed(0)}`}
      {pctStr && <span className="opacity-80"> ({pctStr})</span>}
    </span>
  );
}
PnlSpan.propTypes = { val: PropTypes.number, pct: PropTypes.number, isKrw: PropTypes.bool };

export default function PortfolioBanner() {
  const { data: btc } = usePolling(getBtcPortfolio, 30000);
  const { data: kr }  = usePolling(getStockPortfolio, 30000);
  const { data: us }  = usePolling(getUsPositions, 60000);

  // BTC: krw_balance (현금) + total_eval (포지션 현재가)
  const btcCash  = btc?.summary?.krw_balance ?? 0;
  const btcPos   = btc?.summary?.total_eval  ?? 0;
  const btcEval  = btcCash + btcPos;
  const btcPnl   = btc?.summary?.unrealized_pnl ?? null;
  const btcPnlPct = btc?.summary?.unrealized_pnl_pct ?? null;
  const btcHasPos = (btc?.summary?.open_count ?? 0) > 0;

  // KR: estimated_asset (예수금+평가금합계), cumulative_pnl (미실현)
  const krEval    = kr?.estimated_asset ?? 0;
  const krPnl     = kr?.cumulative_pnl  ?? null;
  const krPnlPct  = kr?.cumulative_pnl_pct ?? null;
  const krOffline = !kr || kr.error || krEval === 0;
  const krIsOpen  = kr?.is_market_open ?? false;

  // US: DRY-RUN — USD only, excluded from KRW total
  const usEval    = us?.summary?.total_current ?? 0;
  const usPnl     = us?.summary?.total_pnl_usd ?? null;
  const usPnlPct  = us?.summary?.total_pnl_pct ?? null;
  const usHasPos  = (us?.summary?.count ?? 0) > 0;

  // 합계 (KRW 기준: BTC + KR만)
  const totalKrw = btcEval + krEval;
  const totalPnl = (btcPnl ?? 0) + (krPnl ?? 0);
  const totalBase = totalKrw - totalPnl;
  const totalPct  = totalBase > 0 ? (totalPnl / totalBase) * 100 : 0;
  const totalPos  = totalPnl >= 0;

  const btcShare = totalKrw > 0 ? (btcEval / totalKrw) * 100 : 0;
  const krShare  = totalKrw > 0 ? (krEval  / totalKrw) * 100 : 0;

  return (
    <div className="border-b border-border bg-card/30 backdrop-blur-sm">
      <div className="px-4 lg:px-6 py-3 flex flex-wrap items-start gap-x-8 gap-y-2">

        {/* 총 자산 + 트리뷰 */}
        <div>
          {/* 총 자산 헤더 */}
          <div className="flex items-baseline gap-3 mb-1.5">
            <div>
              <div className="data-label text-[10px] mb-0.5">총 자산 (KRW)</div>
              <span className="text-xl font-bold font-mono text-text-primary leading-none">
                {fmtKrw(totalKrw)}
              </span>
            </div>
            {totalKrw > 0 && (
              <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                totalPos ? "bg-profit/15 text-profit" : "bg-loss/15 text-loss"
              }`}>
                {totalPos ? "+" : ""}{fmtKrw(totalPnl)} ({fmtPct(totalPct)})
              </span>
            )}
          </div>

          {/* 트리뷰 */}
          <div className="font-mono text-xs space-y-0.5">
            {/* BTC */}
            <div className="flex items-center gap-2 text-text-secondary">
              <span className="text-text-muted select-none">├──</span>
              <span className="text-amber-400 font-semibold w-5">BTC</span>
              <span>{fmtKrw(btcEval)}</span>
              <span className="text-text-muted">({btcShare.toFixed(0)}%)</span>
              {btcHasPos ? (
                <PnlSpan val={btcPnl} pct={btcPnlPct} isKrw />
              ) : (
                <span className="text-text-muted">대기 중</span>
              )}
            </div>

            {/* KR */}
            <div className="flex items-center gap-2 text-text-secondary">
              <span className="text-text-muted select-none">├──</span>
              <span className="text-blue-400 font-semibold w-5">KR</span>
              <span>{fmtKrw(krEval)}</span>
              <span className="text-text-muted">({krShare.toFixed(0)}%)</span>
              {krOffline ? (
                <span className="text-yellow-400">
                  모의투자 · {krIsOpen ? "장중" : "장마감"}
                </span>
              ) : (
                <PnlSpan val={krPnl} pct={krPnlPct} isKrw />
              )}
            </div>

            {/* US */}
            <div className="flex items-center gap-2 text-text-secondary">
              <span className="text-text-muted select-none">└──</span>
              <span className="text-emerald-400 font-semibold w-5">US</span>
              <span>{fmtUsd(usEval)}</span>
              <span className="text-text-muted">(0%)</span>
              {usHasPos ? (
                <PnlSpan val={usPnl} pct={usPnlPct} isKrw={false} />
              ) : (
                <span className="text-yellow-400">DRY-RUN</span>
              )}
            </div>
          </div>
        </div>

        <div className="hidden md:block w-px self-stretch bg-border my-0.5" />

        {/* 자산 배분 바 */}
        <div className="hidden md:block min-w-[140px] pt-0.5">
          <div className="data-label text-[10px] mb-2">자산 배분</div>
          <div className="w-full h-1.5 rounded-full overflow-hidden bg-card/50 border border-border/50 flex">
            <div
              className="bg-amber-400 transition-all duration-700"
              style={{ width: `${btcShare}%` }}
              title={`BTC ${btcShare.toFixed(0)}%`}
            />
            <div
              className="bg-blue-400 transition-all duration-700"
              style={{ width: `${krShare}%` }}
              title={`KR ${krShare.toFixed(0)}%`}
            />
            <div className="bg-emerald-400/30 flex-1" title="US DRY-RUN" />
          </div>
          <div className="flex gap-3 mt-1.5 text-[10px] text-text-muted">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
              BTC {btcShare.toFixed(0)}%
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 inline-block" />
              KR {krShare.toFixed(0)}%
            </span>
            <span className="flex items-center gap-1 opacity-40">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
              US
            </span>
          </div>
        </div>

        {/* 우측 — 시장별 손익 요약 */}
        <div className="hidden lg:flex items-start gap-5 ml-auto pt-0.5">
          <div className="text-right">
            <div className="data-label text-[10px] mb-1">BTC 손익</div>
            {btcHasPos
              ? <PnlSpan val={btcPnl} pct={btcPnlPct} isKrw />
              : <span className="text-[10px] text-text-muted">포지션 없음</span>}
          </div>
          <div className="w-px self-stretch bg-border/50" />
          <div className="text-right">
            <div className="data-label text-[10px] mb-1">KR 손익</div>
            {krOffline
              ? <span className="text-[10px] text-yellow-400">장마감</span>
              : <PnlSpan val={krPnl} pct={krPnlPct} isKrw />}
          </div>
          <div className="w-px self-stretch bg-border/50" />
          <div className="text-right">
            <div className="data-label text-[10px] mb-1">US 손익</div>
            {usHasPos
              ? <PnlSpan val={usPnl} pct={usPnlPct} isKrw={false} />
              : <span className="text-[10px] text-yellow-400">DRY-RUN</span>}
          </div>
        </div>

      </div>
    </div>
  );
}
