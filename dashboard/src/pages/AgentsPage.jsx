import {
  Activity,
  AlertTriangle,
  BarChart2,
  Brain,
  CheckCircle2,
  Globe2,
  Landmark,
  Bitcoin,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { useMemo } from "react";
import { getBtcComposite, getKrComposite, getUsComposite, getRiskPortfolio } from "../api";
import usePolling from "../hooks/usePolling";
import { useLang } from "../hooks/useLang";
import GlassCard from "../components/ui/GlassCard";
import LoadingSkeleton from "../components/ui/LoadingSkeleton";
import StatusBadge from "../components/ui/StatusBadge";

// ── helpers ──────────────────────────────────────────────────────────────────

function MetricRow({ label, value, sub, highlight }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 0",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
      }}
    >
      <span className="subtle" style={{ fontSize: 13 }}>{label}</span>
      <span
        style={{
          fontWeight: 700,
          fontSize: 14,
          color: highlight
            ? highlight === "ok"
              ? "var(--profit)"
              : "var(--loss)"
            : "var(--text-primary)",
        }}
      >
        {value}
        {sub ? (
          <span className="subtle" style={{ fontWeight: 400, marginLeft: 6, fontSize: 12 }}>
            {sub}
          </span>
        ) : null}
      </span>
    </div>
  );
}

function StatusIcon({ ok }) {
  return ok ? (
    <CheckCircle2 size={16} color="var(--profit)" />
  ) : (
    <XCircle size={16} color="var(--loss)" />
  );
}

function MarketStatusCard({ icon: Icon, label, composite, loading }) {
  const { t } = useLang();

  if (loading) return <LoadingSkeleton height={200} />;

  const regime = composite?.regime || composite?.trend || "UNKNOWN";
  const dailyLossPct = composite?.daily_loss_pct ?? null;
  const isLossExceeded = composite?.is_daily_loss_exceeded ?? false;
  const signal = composite?.signal || composite?.final_signal || "—";
  const todayTrades = composite?.today_trades ?? composite?.today_count ?? "—";
  const winRate = composite?.win_rate ?? composite?.cumulative_win_rate ?? null;

  return (
    <GlassCard className="card-pad">
      <div className="panel-title">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon size={18} />
          <h2>{label}</h2>
        </div>
        <StatusBadge status={regime} />
      </div>

      <MetricRow
        label={t("Signal")}
        value={signal}
      />
      <MetricRow
        label={t("Today Trades")}
        value={todayTrades}
      />
      {winRate !== null && (
        <MetricRow
          label={t("Win Rate")}
          value={`${Number(winRate).toFixed(1)}%`}
          highlight={Number(winRate) >= 50 ? "ok" : "warn"}
        />
      )}
      {dailyLossPct !== null && (
        <MetricRow
          label={t("Daily PnL")}
          value={`${Number(dailyLossPct).toFixed(2)}%`}
          highlight={isLossExceeded ? "warn" : "ok"}
        />
      )}
      {(composite?.last_run || composite?.updated_at) && (
        <div className="subtle" style={{ fontSize: 12, marginTop: 8, display: "flex", justifyContent: "space-between" }}>
          <span>{t("Last Run")}</span>
          <span className="mono">{new Date(composite.last_run || composite.updated_at).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      )}
      {isLossExceeded && (
        <div
          style={{
            marginTop: 10,
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.3)",
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 13,
            color: "var(--red)",
          }}
        >
          <AlertTriangle size={14} />
          {t("Daily loss limit exceeded — trading halted")}
        </div>
      )}
    </GlassCard>
  );
}

// ── main ──────────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { t } = useLang();

  const { data: risk, loading: riskLoading } = usePolling(getRiskPortfolio, 60000);
  const { data: btc, loading: btcLoading } = usePolling(getBtcComposite, 30000);
  const { data: kr, loading: krLoading } = usePolling(getKrComposite, 30000);
  const { data: us, loading: usLoading } = usePolling(getUsComposite, 30000);

  const riskData = useMemo(() => risk?.data || risk || null, [risk]);

  const regime = riskData?.regime || "UNKNOWN";
  const mdd = riskData?.mdd ?? null;
  const driftStatus = riskData?.drift_status || "NO_DATA";
  const icHealth = riskData?.ic_health ?? null;
  const dailyVar = riskData?.daily_var ?? null;

  const driftOk = driftStatus === "OK" || driftStatus === "STABLE";
  const icActiveRatio =
    icHealth && icHealth.total_weights > 0
      ? icHealth.active_weights / icHealth.total_weights
      : null;

  return (
    <div className="stack">
      <div className="page-heading">
        <div>
          <h1>{t("System Status")}</h1>
          <p>{t("Cross-market risk, regime, ML drift, and IC health at a glance.")}</p>
        </div>
      </div>

      {/* ── Top summary row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14 }}>
        {/* Regime */}
        <GlassCard className="card-pad" style={{ textAlign: "center" }}>
          <div className="subtle" style={{ fontSize: 12, marginBottom: 8 }}>{t("Market Regime")}</div>
          {riskLoading ? (
            <LoadingSkeleton height={32} />
          ) : (
            <StatusBadge status={regime} />
          )}
        </GlassCard>

        {/* MDD */}
        <GlassCard className="card-pad" style={{ textAlign: "center" }}>
          <div className="subtle" style={{ fontSize: 12, marginBottom: 8 }}>{t("Max Drawdown")}</div>
          {riskLoading ? (
            <LoadingSkeleton height={32} />
          ) : (
            <div
              style={{
                fontSize: 22,
                fontWeight: 800,
                color: mdd !== null && mdd < -10 ? "var(--red)" : "var(--text-primary)",
              }}
            >
              {mdd !== null ? `${Number(mdd).toFixed(1)}%` : "—"}
            </div>
          )}
        </GlassCard>

        {/* Daily VaR */}
        <GlassCard className="card-pad" style={{ textAlign: "center" }}>
          <div className="subtle" style={{ fontSize: 12, marginBottom: 8 }}>{t("Daily VaR (95%)")}</div>
          {riskLoading ? (
            <LoadingSkeleton height={32} />
          ) : (
            <div style={{ fontSize: 22, fontWeight: 800 }}>
              {dailyVar !== null ? `${Number(dailyVar).toFixed(2)}%` : "—"}
            </div>
          )}
        </GlassCard>

        {/* ML Drift */}
        <GlassCard className="card-pad" style={{ textAlign: "center" }}>
          <div className="subtle" style={{ fontSize: 12, marginBottom: 8 }}>{t("ML Drift")}</div>
          {riskLoading ? (
            <LoadingSkeleton height={32} />
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              <StatusIcon ok={driftOk} />
              <span style={{ fontWeight: 700, fontSize: 14 }}>{driftStatus}</span>
            </div>
          )}
        </GlassCard>

        {/* IC Health */}
        <GlassCard className="card-pad" style={{ textAlign: "center" }}>
          <div className="subtle" style={{ fontSize: 12, marginBottom: 8 }}>{t("IC Active Weights")}</div>
          {riskLoading ? (
            <LoadingSkeleton height={32} />
          ) : (
            <div style={{ fontSize: 22, fontWeight: 800 }}>
              {icHealth
                ? `${icHealth.active_weights} / ${icHealth.total_weights}`
                : "—"}
            </div>
          )}
          {icActiveRatio !== null && (
            <div
              className="subtle"
              style={{ fontSize: 12, marginTop: 4 }}
            >
              {`${(icActiveRatio * 100).toFixed(0)}% active`}
            </div>
          )}
        </GlassCard>
      </div>

      {/* ── Per-market status ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
        <MarketStatusCard
          icon={Bitcoin}
          label="BTC"
          composite={btc}
          loading={btcLoading}
        />
        <MarketStatusCard
          icon={Landmark}
          label="KR"
          composite={kr}
          loading={krLoading}
        />
        <MarketStatusCard
          icon={Globe2}
          label="US"
          composite={us}
          loading={usLoading}
        />
      </div>

      {/* ── Risk / Research Loop detail ── */}
      <div className="tv-grid">
        <div className="tv-main">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Risk Parameters")}</h2>
              <Activity size={18} color="var(--text-secondary)" />
            </div>
            {riskLoading ? (
              <LoadingSkeleton height={180} />
            ) : (
              <>
                <MetricRow
                  label={t("Total Assets (KRW)")}
                  value={riskData?.total_assets != null
                    ? `₩${Number(riskData.total_assets).toLocaleString()}`
                    : "—"}
                />
                <MetricRow
                  label="BTC"
                  value={riskData?.btc_value != null
                    ? `₩${Number(riskData.btc_value).toLocaleString()}`
                    : "—"}
                />
                <MetricRow
                  label="KR"
                  value={riskData?.kr_value != null
                    ? `₩${Number(riskData.kr_value).toLocaleString()}`
                    : "—"}
                />
                <MetricRow
                  label="US"
                  value={riskData?.us_value != null
                    ? `₩${Number(riskData.us_value).toLocaleString()}`
                    : "—"}
                />
                <MetricRow
                  label={t("Max Drawdown")}
                  value={mdd !== null ? `${Number(mdd).toFixed(2)}%` : "—"}
                  highlight={mdd !== null && mdd < -10 ? "warn" : "ok"}
                />
                <MetricRow
                  label={t("Daily VaR (95%)")}
                  value={dailyVar !== null ? `${Number(dailyVar).toFixed(2)}%` : "—"}
                />
              </>
            )}
          </GlassCard>
        </div>

        <aside className="tv-side">
          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("Research Loop Schedule")}</h2>
              <Brain size={18} color="var(--text-secondary)" />
            </div>
            <div className="stack" style={{ gap: 14 }}>
              {[
                { name: "Alpha Researcher", schedule: "Sat 22:00 KST", icon: BarChart2 },
                { name: "Signal Evaluator", schedule: "Sun 23:00 KST", icon: TrendingUp },
                { name: "Param Optimizer", schedule: "Sun 23:30 KST", icon: Brain },
                { name: "ML Retrain", schedule: t("Daily 08:30 KST"), icon: Activity },
              ].map(({ name, schedule, icon: Icon }) => (
                <div
                  key={name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.05)",
                  }}
                >
                  <Icon size={15} color="var(--text-secondary)" style={{ flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 13 }}>{t(name)}</div>
                    <div className="subtle" style={{ fontSize: 12, marginTop: 2 }}>{schedule}</div>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="card-pad">
            <div className="panel-title">
              <h2>{t("IC / Signal Health")}</h2>
              <BarChart2 size={18} color="var(--text-secondary)" />
            </div>
            {riskLoading ? (
              <LoadingSkeleton height={100} />
            ) : (
              <>
                <MetricRow
                  label={t("Active Weights")}
                  value={icHealth ? icHealth.active_weights : "—"}
                />
                <MetricRow
                  label={t("Total Weights")}
                  value={icHealth ? icHealth.total_weights : "—"}
                />
                <MetricRow
                  label={t("Coverage")}
                  value={icActiveRatio !== null
                    ? `${(icActiveRatio * 100).toFixed(0)}%`
                    : "—"}
                  highlight={icActiveRatio !== null && icActiveRatio >= 0.5 ? "ok" : "warn"}
                />
                <MetricRow
                  label={t("ML Drift Status")}
                  value={driftStatus}
                  highlight={driftOk ? "ok" : "warn"}
                />
              </>
            )}
          </GlassCard>
        </aside>
      </div>
    </div>
  );
}
