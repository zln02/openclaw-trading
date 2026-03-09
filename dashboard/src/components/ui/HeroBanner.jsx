import { Bitcoin, Bot, Landmark, Wallet } from "lucide-react";
import PropTypes from "prop-types";
import GlassCard from "./GlassCard";
import AnimatedNumber from "./AnimatedNumber";

const ITEMS = [
  { key: "btc", label: "BTC Total Assets", icon: <Bitcoin size={18} /> },
  { key: "kr", label: "KR Total Assets", icon: <Landmark size={18} /> },
  { key: "us", label: "US Total Assets", icon: <Wallet size={18} /> },
  { key: "total", label: "Global Portfolio", icon: <Bot size={18} /> },
];

export default function HeroBanner({ metrics }) {
  return (
    <GlassCard className="card-pad" style={{ marginBottom: 24 }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 20% 10%, rgba(139,92,246,0.18), transparent 24%), radial-gradient(circle at 80% 0%, rgba(59,130,246,0.18), transparent 20%)",
          pointerEvents: "none",
        }}
      />
      <div className="grid-4" style={{ position: "relative" }}>
        {ITEMS.map((item) => {
          const current = metrics[item.key] || { value: 0, delta: 0, prefix: "", suffix: "" };
          const tone = current.delta >= 0 ? "profit" : "loss";
          return (
            <div
              key={item.key}
              style={{
                padding: 18,
                borderRadius: 20,
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--text-secondary)", marginBottom: 18 }}>
                {item.icon}
                <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                  {item.label}
                </span>
              </div>
              <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.04em" }}>
                <AnimatedNumber
                  value={Number(current.value) || 0}
                  prefix={current.prefix || ""}
                  suffix={current.suffix || ""}
                  decimals={current.decimals || 0}
                  className={tone === "profit" ? "profit glow-profit" : "loss glow-loss"}
                />
              </div>
              <div
                style={{
                  marginTop: 12,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  color: tone === "profit" ? "var(--profit)" : "var(--loss)",
                  fontWeight: 700,
                }}
              >
                {current.delta >= 0 ? "+" : ""}
                {Number(current.delta || 0).toFixed(2)}%
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}

HeroBanner.propTypes = {
  metrics: PropTypes.object.isRequired,
};
