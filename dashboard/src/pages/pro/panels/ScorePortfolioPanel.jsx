import LoadingSkeleton from "../../../components/ui/LoadingSkeleton";
import ScoreRadial from "../../../components/ui/ScoreRadial";
import { krw, pct } from "../../../lib/format";
import { useProData } from "../ProDataContext";

function scoreLabel(score) {
  if (score <= 30) return "리스크 오프";
  if (score <= 70) return "중립";
  return "리스크 온";
}

export default function ScorePortfolioPanel() {
  const { composite, portfolio } = useProData();

  if (composite?.loading && !composite?.data) {
    return <LoadingSkeleton height={300} />;
  }

  const score = Number(
    composite?.data?.composite_score ??
      composite?.data?.score ??
      composite?.data?.final_score ??
      0,
  );
  const summary = portfolio?.summary || {};
  const estimatedAsset = Number(summary.estimated_asset || 0);
  const unrealizedPnl = Number(summary.unrealized_pnl || 0);
  const unrealizedPct = Number(summary.unrealized_pnl_pct || 0);
  const winrate = Number(summary.winrate || 0);
  const wins = Number(summary.wins || 0);
  const losses = Number(summary.losses || 0);
  const isProfitable = unrealizedPct >= 0;

  return (
    <div className="flex h-full flex-col gap-3 bg-[color:var(--bg-primary)] p-3">
      <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
        <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
          종합 점수
        </div>
        <div className="mt-2">
          <ScoreRadial score={score} />
        </div>
        <div className="mt-2 text-center text-xs text-[color:var(--text-secondary)]">
          {scoreLabel(score)}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2">
        <Stat label="총 자산" value={krw(estimatedAsset)} />
        <Stat
          label="미실현 손익"
          value={krw(unrealizedPnl)}
          sub={pct(unrealizedPct)}
          tone={isProfitable ? "profit" : "loss"}
        />
        <Stat
          label="승률"
          value={`${winrate.toFixed(1)}%`}
          sub={`${wins}승 ${losses}패`}
        />
      </div>
    </div>
  );
}

function Stat({ label, value, sub, tone }) {
  const toneClass =
    tone === "profit"
      ? "text-[color:var(--color-profit)]"
      : tone === "loss"
        ? "text-[color:var(--color-loss)]"
        : "text-[color:var(--text-primary)]";
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
        {label}
      </div>
      <div className={`mt-1 numeric text-sm font-semibold ${toneClass}`}>{value}</div>
      {sub != null ? (
        <div className={`mt-0.5 numeric text-[11px] ${toneClass}`}>{sub}</div>
      ) : null}
    </div>
  );
}
