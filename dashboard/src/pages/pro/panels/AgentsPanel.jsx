import Badge from "../../../components/ui/Badge";
import { EmptyState } from "../../../components/ui/PageState";
import { compactTime } from "../../../lib/format";
import { useProData } from "../ProDataContext";

function normalizeAction(action) {
  return String(action || "HOLD").toUpperCase();
}

function actionVariant(action) {
  const a = normalizeAction(action);
  if (a === "BUY") return "buy";
  if (a === "SELL") return "sell";
  return "hold";
}

function scoreColor(score) {
  if (score >= 70) return "var(--color-profit)";
  if (score >= 30) return "var(--color-warning)";
  return "var(--color-loss)";
}

export default function AgentsPanel() {
  const { decisionLog } = useProData();
  const rows = decisionLog?.data?.decisions || [];

  if (rows.length === 0) {
    return (
      <div className="p-3">
        <EmptyState message="에이전트 결정 로그가 비어 있습니다" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto bg-[color:var(--bg-primary)] scrollbar-subtle">
      <div className="divide-y divide-white/5">
        {rows.map((row, index) => {
          const action = normalizeAction(row.action);
          const rowScore =
            row.composite_score ?? row.score ?? row.signal_score ?? null;
          return (
            <div
              key={row.id || row.created_at || index}
              className="flex items-start gap-3 px-3 py-2.5 transition-colors hover:bg-white/[0.015]"
            >
              <span className="numeric w-14 flex-shrink-0 pt-0.5 text-[11px] text-[color:var(--text-muted)]">
                {compactTime(row.created_at || row.timestamp)}
              </span>
              <div className="flex-shrink-0 pt-0.5">
                <Badge variant={actionVariant(action)}>{action}</Badge>
              </div>
              {rowScore != null ? (
                <span
                  className="numeric flex-shrink-0 pt-0.5 text-[11px] font-semibold"
                  style={{ color: scoreColor(Number(rowScore)) }}
                >
                  {Number(rowScore).toFixed(0)}
                </span>
              ) : null}
              <p className="line-clamp-2 min-w-0 text-xs text-[color:var(--text-secondary)]">
                {row.reason || row.reasoning || "판단 근거 없음"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
