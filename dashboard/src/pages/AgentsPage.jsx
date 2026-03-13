import { AlertTriangle, Bot, BrainCircuit, FileSearch, GitBranch, Shield, TimerReset } from "lucide-react";
import { useMemo, useState } from "react";
import { getAgentDecisions, getAgentPerformance } from "../api";
import usePolling from "../hooks/usePolling";
import { compactTime, pct, relativeTime } from "../lib/format";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState } from "../components/ui/PageState";

const AGENTS = [
  { key: "orchestrator", name: "오케스트레이터", model: "Claude Opus", icon: Bot },
  { key: "market_analyst", name: "마켓 애널리스트", model: "Claude Sonnet", icon: BrainCircuit },
  { key: "news_analyst", name: "뉴스 애널리스트", model: "Claude Sonnet", icon: FileSearch },
  { key: "risk_manager", name: "리스크 매니저", model: "Claude Opus", icon: Shield },
  { key: "reporter", name: "리포터", model: "Claude Sonnet", icon: GitBranch },
];

function actionVariant(action) {
  const normalized = String(action || "HOLD").toUpperCase();
  if (normalized === "BUY") return "buy";
  if (normalized === "SELL") return "sell";
  if (normalized === "SKIP") return "warning";
  return "hold";
}

export default function AgentsPage() {
  const { data, loading } = usePolling(() => getAgentDecisions(20), 30000);
  const { data: performanceData, loading: performanceLoading } = usePolling(() => getAgentPerformance("weekly"), 60000);
  const [expanded, setExpanded] = useState(null);
  const decisions = useMemo(() => data?.decisions || [], [data]);
  const performance = useMemo(() => performanceData?.performance || performanceData?.items || [], [performanceData]);

  const latestByAgent = useMemo(() => {
    const map = new Map();
    decisions.forEach((decision) => {
      const key = String(decision.agent_name || "").toLowerCase();
      if (!map.has(key)) {
        map.set(key, decision);
      }
    });
    return map;
  }, [decisions]);

  return (
    <div className="grid gap-[var(--content-gap)] xl:grid-cols-[minmax(0,1.25fr)_360px]">
      <Card title="의사결정 타임라인" icon={<TimerReset size={14} />} delay={0}>
        {loading ? (
          <LoadingSkeleton height={520} />
        ) : (
          <div className="space-y-3">
            {decisions.slice(0, 20).map((decision, index) => {
              const isOpen = expanded === index;
              const action = decision.action || decision.decision || "HOLD";
              const hasConflict = Boolean(decision.conflict) || String(decision.decision_type || "").includes("conflict");
              return (
                <button
                  key={decision.id || index}
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : index)}
                  className="w-full rounded-xl border border-white/5 bg-white/[0.02] px-4 py-4 text-left transition hover:border-white/10"
                >
                  <div className="grid gap-[var(--content-gap)] md:grid-cols-[130px_110px_minmax(0,1fr)]">
                    <div className="numeric text-xs text-[color:var(--text-muted)]">{compactTime(decision.created_at || decision.timestamp)}</div>
                    <div className="flex items-center gap-2">
                      {hasConflict ? <AlertTriangle size={14} className="text-[color:var(--color-warning)]" /> : null}
                      <Badge variant={actionVariant(action)}>{String(action).toUpperCase()}</Badge>
                    </div>
                    <div>
                      <div className="font-medium text-[color:var(--text-primary)]">
                        {(decision.agent_name || "agent").replaceAll("_", " ")} · {(decision.market || "market").toUpperCase()}
                      </div>
                      <div className="mt-1 text-sm text-[color:var(--text-secondary)]">
                        {decision.reasoning || "의사결정 근거가 기록되지 않았습니다."}
                      </div>
                    </div>
                  </div>
                  {isOpen ? (
                    <div className="mt-3 border-t border-white/5 pt-3 text-sm text-[color:var(--text-secondary)]">
                      <span className="numeric">신뢰도 {decision.confidence != null ? `${Number(decision.confidence).toFixed(2)}` : "—"}</span>
                      {" · "}
                      {decision.result || decision.decision_type || "추가 결과 없음"}
                    </div>
                  ) : null}
                </button>
              );
            })}
            {decisions.length === 0 ? <EmptyState message="기록된 에이전트 의사결정이 없습니다." /> : null}
          </div>
        )}
      </Card>

      <div className="space-y-[var(--content-gap)]">
        <Card title="에이전트 상태" icon={<Bot size={14} />} delay={1}>
          <div className="space-y-3">
            {AGENTS.map(({ key, name, model, icon: Icon }) => {
              const latest = latestByAgent.get(key);
              const recent = latest?.created_at || latest?.timestamp;
              const active = recent ? Date.now() - new Date(recent).getTime() < 1000 * 60 * 60 * 6 : false;
              return (
                <div key={name} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="grid h-9 w-9 place-items-center rounded-xl border border-white/10 bg-white/[0.03]">
                        <Icon size={16} />
                      </div>
                      <div>
                        <div className="font-medium text-[color:var(--text-primary)]">{name}</div>
                        <div className="text-xs text-[color:var(--text-muted)]">{model}</div>
                      </div>
                    </div>
                    <Badge variant={active ? "profit" : "neutral"}>{active ? "활성" : "대기"}</Badge>
                  </div>
                  <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                    마지막 동작: <span className="numeric">{recent ? relativeTime(recent) : "기록 없음"}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card title="주간 성능" icon={<Shield size={14} />} delay={2}>
          {performanceLoading ? (
            <LoadingSkeleton height={220} />
          ) : performance.length === 0 ? (
            <EmptyState message="주간 에이전트 성능 데이터가 없습니다." />
          ) : (
            <div className="space-y-3">
              {performance.slice(0, 5).map((item, index) => (
                <div key={item.id || `${item.agent_name}-${index}`} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-[color:var(--text-primary)]">
                        {(item.agent_name || "agent").replaceAll("_", " ")}
                      </div>
                      <div className="text-xs text-[color:var(--text-muted)]">
                        {String(item.market || "all").toUpperCase()} · 신호 {item.total_signals ?? 0}건
                      </div>
                    </div>
                    <Badge variant={Number(item.accuracy || 0) >= 0.5 ? "profit" : "warning"}>
                      {pct(Number(item.accuracy || 0) * 100)}
                    </Badge>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-[color:var(--text-secondary)]">
                    <div className="numeric">PnL 기여 {Number(item.pnl_contribution || 0).toFixed(2)}</div>
                    <div className="numeric">평균 신뢰도 {Number(item.avg_confidence || 0).toFixed(2)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="리서치 루프" icon={<GitBranch size={14} />} delay={3}>
          <div className="space-y-3">
            {[
              ["알파 리서처", "토 22:00"],
              ["시그널 평가기", "일 23:00"],
              ["파라미터 옵티마이저", "일 23:30"],
            ].map(([name, time]) => (
              <div key={name} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                <div className="font-medium text-[color:var(--text-primary)]">{name}</div>
                <div className="mt-1 text-sm text-[color:var(--text-secondary)]">최근 예약 실행: {time}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
