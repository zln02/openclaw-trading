import { Bot, BrainCircuit, FileSearch, GitBranch, Shield, TimerReset } from "lucide-react";
import { useMemo, useState } from "react";
import { getAgentDecisions } from "../api";
import usePolling from "../hooks/usePolling";
import { useLang } from "../hooks/useLang";
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
  const { t } = useLang();
  const { data, loading } = usePolling(() => getAgentDecisions(20), 30000);
  const [expanded, setExpanded] = useState(null);
  const decisions = useMemo(() => data?.decisions || [], [data]);

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>{t("AI Agent Operations")}</h1>
          <p>{t("Specialist-agent orchestration, decision traces, and research loop visibility for trading supervision.")}</p>
        </div>
      </div>

      <div className="tv-grid">
        <div className="tv-main tv-stack">
          <GlassCard className="card-pad">
            <div className="symbol-header">
              <div>
                <div className="symbol-code">{t("AGENT DESK")}</div>
                <div className="symbol-meta">
                  <span className="toolbar-chip">{t("Decision Feed")}</span>
                  <span className="toolbar-chip">{t("Last 20")}</span>
                  <span className="toolbar-chip mono">{decisions.length} Events</span>
                </div>
              </div>
            </div>
            <div className="panel-title">
              <h2>{t("Decision Timeline")}</h2>
              <TimerReset size={18} color="var(--text-secondary)" />
            </div>
            {loading ? (
              <LoadingSkeleton height={420} />
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
                        background: "rgba(255,255,255,0.02)",
                        borderRadius: 10,
                        padding: 14,
                        color: "inherit",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ display: "grid", gridTemplateColumns: "160px 100px 1fr", gap: 16, alignItems: "start" }}>
                        <div className="mono subtle">{compactTime(decision.created_at)}</div>
                        <StatusBadge status={decision.decision || "TRANSITION"} />
                        <div>
                          <strong>{decision.market?.toUpperCase?.() || "MARKET"}</strong>
                          <div className="subtle" style={{ marginTop: 8 }}>
                            {decision.reasoning || t("No reasoning attached.")}
                          </div>
                        </div>
                      </div>
                      {isOpen ? (
                        <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                          <div className="subtle">{t("Confidence:")} {decision.confidence ?? "—"}%</div>
                          <div style={{ marginTop: 8 }}>{decision.details || decision.reasoning || t("No extra agent details.")}</div>
                        </div>
                      ) : null}
                    </button>
                  );
                })}
                {decisions.length === 0 ? <EmptyState message={t("No agent decisions recorded.")} /> : null}
              </div>
            )}
          </GlassCard>
        </div>

        <aside className="tv-side">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Agent Team Topology")}</h2>
              <Bot size={18} color="var(--text-secondary)" />
            </div>
            <div className="agent-topology">
              {AGENTS.map(({ name, model, icon: Icon }, index) => (
                <div key={name} className="agent-node">
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <Icon size={18} />
                    <strong>{t(name)}</strong>
                  </div>
                  <div className="subtle">{t(model)}</div>
                  <div style={{ marginTop: 12 }}>
                    <StatusBadge status={index === 3 ? "RISK_ON" : "TRANSITION"} />
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Level 5 Research Loop")}</h2>
              <GitBranch size={18} color="var(--text-secondary)" />
            </div>
            <div className="stack" style={{ gap: 14 }}>
              {[
                ["Alpha Researcher", "Sat 22:00"],
                ["Signal Evaluator", "Sun 23:00"],
                ["Param Optimizer", "Sun 23:30"],
              ].map(([name, time]) => (
                <div key={name} className="agent-node">
                  <div style={{ fontWeight: 700 }}>{t(name)}</div>
                  <div className="subtle" style={{ marginTop: 6 }}>{t("Last scheduled run:")} {time}</div>
                </div>
              ))}
              <div className="agent-node">
                <div style={{ fontWeight: 700, marginBottom: 8 }}>{t("weights.json snapshot")}</div>
                <div className="subtle mono" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                  {`btc_momentum: 0.34\nkr_ml_overlay: 0.22\nus_breakout: 0.18\nrisk_overlay: 0.26`}
                </div>
              </div>
            </div>
          </GlassCard>
        </aside>
      </div>
    </div>
  );
}
