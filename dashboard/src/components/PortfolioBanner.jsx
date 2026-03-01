import PropTypes from "prop-types";
import usePolling from "../hooks/usePolling";
import { getBtcPortfolio, getKrPortfolio } from "../api";

const fmt = (n) => n != null ? Number(n).toLocaleString() : "—";

function fmtPct(n) {
  if (n == null) return null;
  return `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%`;
}

function PnlBadge({ val }) {
  if (val == null) return <span className="text-text-secondary text-sm">—</span>;
  const pos = val >= 0;
  return (
    <span className={`font-mono font-medium text-sm ${pos ? "text-profit" : "text-loss"}`}>
      {pos ? "+" : ""}₩{fmt(val)}
    </span>
  );
}
PnlBadge.propTypes = { val: PropTypes.number };

export default function PortfolioBanner() {
  const { data: btc } = usePolling(getBtcPortfolio, 30000);
  const { data: kr }  = usePolling(getKrPortfolio, 30000);

  const btcEval = btc?.summary?.total_eval    ?? 0;
  const krEval  = kr?.summary?.total_eval     ?? 0;
  const btcPnl  = btc?.summary?.unrealized_pnl ?? 0;
  const krPnl   = kr?.summary?.unrealized_pnl  ?? 0;

  const totalKrw  = btcEval + krEval;
  const totalPnl  = btcPnl + krPnl;
  const totalBase = totalKrw - totalPnl;
  const totalPct  = totalBase > 0 ? (totalPnl / totalBase) * 100 : 0;

  const btcShare = totalKrw > 0 ? (btcEval / totalKrw) * 100 : 0;
  const krShare  = totalKrw > 0 ? (krEval  / totalKrw) * 100 : 0;
  const isPos    = totalPnl >= 0;
  const pctStr   = fmtPct(totalPct);

  return (
    <div className="border-b border-border bg-card/30 backdrop-blur-sm">
      <div className="px-4 lg:px-6 py-3 flex flex-wrap items-center gap-x-8 gap-y-3">

        {/* 총 자산 */}
        <div>
          <div className="data-label mb-0.5">총 자산 (KRW)</div>
          <div className="text-2xl font-bold font-mono text-text-primary leading-none">
            ₩{fmt(totalKrw)}
          </div>
        </div>

        <div className="h-10 w-px bg-border hidden sm:block" />

        {/* 미실현 손익 */}
        <div>
          <div className="data-label mb-0.5">미실현 손익</div>
          <div className="flex items-center gap-2 leading-none">
            <span className={`text-lg font-bold font-mono ${isPos ? "text-profit" : "text-loss"}`}>
              {isPos ? "+" : ""}₩{fmt(totalPnl)}
            </span>
            {pctStr && (
              <span className={`text-sm font-mono px-1.5 py-0.5 rounded ${isPos ? "bg-profit/15 text-profit" : "bg-loss/15 text-loss"}`}>
                {pctStr}
              </span>
            )}
          </div>
        </div>

        <div className="h-10 w-px bg-border hidden md:block" />

        {/* 자산 배분 바 */}
        <div className="flex-1 min-w-[180px]">
          <div className="data-label mb-1.5">자산 배분</div>
          <div className="w-full h-2 rounded-full overflow-hidden bg-card/50 border border-border/50 flex">
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
            <div
              className="bg-emerald-400/40 flex-1"
              title="US DRY-RUN"
            />
          </div>
          <div className="flex gap-4 mt-1 text-xs text-text-secondary">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
              BTC {btcShare.toFixed(0)}%
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-400 inline-block" />
              KR {krShare.toFixed(0)}%
            </span>
            <span className="flex items-center gap-1 opacity-50">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
              US DRY-RUN
            </span>
          </div>
        </div>

        {/* 시장별 개별 손익 */}
        <div className="hidden lg:flex items-center gap-6">
          <div>
            <div className="data-label mb-0.5">BTC 손익</div>
            <PnlBadge val={btcPnl} />
          </div>
          <div>
            <div className="data-label mb-0.5">KR 손익</div>
            <PnlBadge val={krPnl} />
          </div>
        </div>

      </div>
    </div>
  );
}
