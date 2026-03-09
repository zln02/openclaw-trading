import { Bot, BrainCircuit, FileSearch, GitBranch, Shield, TimerReset } from "lucide-react";
import { useMemo, useState } from "react";
import { getAgentDecisions } from "../api";
import usePolling from "../hooks/usePolling";
import { compactTime } from "../lib/format";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import { EmptyState } from "../components/ui/PageState";
import StatusBadge from "../components/ui/StatusBadge";

const AGENTS = [
  { name: "Orchestrator", model: "Claude Opus", icon: Bot },
  { name: "Market Analyst", model: "Claude Sonnet", icon: BrainCircuit },
  { name: "News Analyst", model: "Claude Sonnet", icon: FileSearch },
  { name: "Risk Manager", model: "Claude Opus", icon: Shield },
  { name: "Reporter", model: "Claude Sonnet", icon: GitBranch },
];

export default function AgentsPage() {
  const { data, loading } = usePolling(() => getAgentDecisions(20), 30000);
  const [expanded, setExpanded] = useState(null);
  const decisions = useMemo(() => data?.decisions || [], [data]);

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>AI Agent Operations</h1>
          <p>Specialist-agent orchestration, decision traces, and research loop visibility for trading supervision.</p>
        </div>
      </div>

      <div className="page-grid">
        <div className="col-12">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Agent Team Topology</h2>
              <Bot size={18} color="var(--text-secondary)" />
            </div>
            <div className="grid-4" style={{ alignItems: "stretch" }}>
              {AGENTS.map(({ name, model, icon: Icon }, index) => (
                <div
                  key={name}
                  style={{
                    padding: 18,
                    borderRadius: 18,
                    background: index === 0 ? "linear-gradient(135deg, rgba(139,92,246,0.2), rgba(59,130,246,0.14))" : "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <Icon size={18} />
                    <strong>{name}</strong>
                  </div>
                  <div className="subtle">{model}</div>
                  <div style={{ marginTop: 14 }}>
                    <StatusBadge status={index === 3 ? "RISK_ON" : "TRANSITION"} />
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>

        <div className="col-8">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Decision Timeline</h2>
              <TimerReset size={18} color="var(--text-secondary)" />
            </div>
            {loading ? (
              <LoadingSkeleton height={380} />
            ) : (
              <div className="stack" style={{ gap: 12 }}>
                {decisions.slice(0, 20).map((decision, index) => {
                  const isOpen = expanded === index;
                  return (
                    <button
                      key={decision.id || index}
                      type="button"
                      onClick={() => setExpanded(isOpen ? null : index)}
                      style={{
                        textAlign: "left",
                        border: "1px solid rgba(255,255,255,0.06)",
                        background: "rgba(255,255,255,0.03)",
                        borderRadius: 18,
                        padding: 16,
                        color: "inherit",
                        cursor: "pointer",
                      }}
                    >
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "180px 100px 1fr",
                          gap: 16,
                          alignItems: "start",
                        }}
                      >
                        <div className="mono subtle">{compactTime(decision.created_at)}</div>
                        <StatusBadge status={decision.decision || "TRANSITION"} />
                        <div>
                          <strong>{decision.market?.toUpperCase?.() || "MARKET"}</strong>
                          <div className="subtle" style={{ marginTop: 8 }}>
                            {decision.reasoning || "No reasoning attached."}
                          </div>
                        </div>
                      </div>
                      {isOpen ? (
                        <div
                          style={{
                            marginTop: 14,
                            paddingTop: 14,
                            borderTop: "1px solid rgba(255,255,255,0.06)",
                          }}
                        >
                          <div className="subtle">Confidence: {decision.confidence ?? "—"}%</div>
                          <div style={{ marginTop: 8 }}>{decision.details || decision.reasoning || "No extra agent details."}</div>
                        </div>
                      ) : null}
                    </button>
                  );
                })}
                {decisions.length === 0 ? <EmptyState message="No agent decisions recorded." /> : null}
              </div>
            )}
          </GlassCard>
        </div>

        <div className="col-4">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>Level 5 Research Loop</h2>
              <GitBranch size={18} color="var(--text-secondary)" />
            </div>
            <div className="stack" style={{ gap: 14 }}>
              {[
                ["Alpha Researcher", "Sat 22:00"],
                ["Signal Evaluator", "Sun 23:00"],
                ["Param Optimizer", "Sun 23:30"],
              ].map(([name, time]) => (
                <div
                  key={name}
                  style={{
                    padding: 14,
                    borderRadius: 16,
                    border: "1px solid rgba(255,255,255,0.06)",
                    background: "rgba(255,255,255,0.03)",
                  }}
                >
                  <div style={{ fontWeight: 700 }}>{name}</div>
                  <div className="subtle" style={{ marginTop: 6 }}>
                    Last scheduled run: {time}
                  </div>
                </div>
              ))}
              <div
                style={{
                  padding: 14,
                  borderRadius: 16,
                  border: "1px solid rgba(255,255,255,0.06)",
                  background: "rgba(255,255,255,0.03)",
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: 8 }}>weights.json snapshot</div>
                <div className="subtle mono" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                  {`btc_momentum: 0.34\nkr_ml_overlay: 0.22\nus_breakout: 0.18\nrisk_overlay: 0.26`}
                </div>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
