import PropTypes from "prop-types";
import GlassCard from "./GlassCard";
import AnimatedNumber from "./AnimatedNumber";
import MiniChart from "./MiniChart";

export default function StatCard({
  label,
  value = 0,
  prefix = "",
  suffix = "",
  decimals = 0,
  delta,
  trend = [],
  icon,
  tone = "neutral",
}) {
  const toneColor =
    tone === "profit" ? "var(--profit)" : tone === "loss" ? "var(--loss)" : "var(--accent-purple)";

  return (
    <GlassCard className="card-pad">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 18 }}>
        <div>
          <div className="subtle" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            {label}
          </div>
          <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.04em", marginTop: 8 }}>
            <AnimatedNumber
              value={Number(value) || 0}
              prefix={prefix}
              suffix={suffix}
              decimals={decimals}
              className={tone === "profit" ? "profit glow-profit" : tone === "loss" ? "loss glow-loss" : ""}
            />
          </div>
        </div>
        {icon ? <div style={{ color: "var(--text-secondary)" }}>{icon}</div> : null}
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            color:
              delta == null
                ? "var(--text-secondary)"
                : delta >= 0
                  ? "var(--profit)"
                  : "var(--loss)",
            fontSize: 13,
            fontWeight: 700,
          }}
        >
          {delta == null ? "No change data" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}%`}
        </div>
        <MiniChart data={trend} color={toneColor} />
      </div>
    </GlassCard>
  );
}

StatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.number,
  prefix: PropTypes.string,
  suffix: PropTypes.string,
  decimals: PropTypes.number,
  delta: PropTypes.number,
  trend: PropTypes.arrayOf(PropTypes.object),
  icon: PropTypes.node,
  tone: PropTypes.oneOf(["neutral", "profit", "loss"]),
};
