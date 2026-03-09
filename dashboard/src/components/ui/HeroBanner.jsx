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
    <GlassCard className="card-pad top-banner glass-card--accent compact-banner status-strip" style={{ marginBottom: 14 }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 20% 10%, rgba(139,92,246,0.18), transparent 24%), radial-gradient(circle at 80% 0%, rgba(59,130,246,0.18), transparent 20%)",
          pointerEvents: "none",
        }}
      />
      <div className="banner-grid">
        {ITEMS.map((item) => {
          const current = metrics[item.key] || { value: 0, delta: 0, prefix: "", suffix: "" };
          const tone = current.delta >= 0 ? "profit" : "loss";
          return (
            <div
              key={item.key}
              className={`banner-item ${item.key === "total" ? "global-card" : ""}`.trim()}
            >
              <div className="metric-label">
                {item.icon}
                <span>{item.label}</span>
              </div>
              <div className="number-glow mono" style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.04em" }}>
                <AnimatedNumber
                  value={Number(current.value) || 0}
                  prefix={current.prefix || ""}
                  suffix={current.suffix || ""}
                  decimals={current.decimals || 0}
                  className={tone === "profit" ? "profit glow-profit" : "loss glow-loss"}
                />
              </div>
              <div className="metric-delta" style={{ color: tone === "profit" ? "var(--profit)" : "var(--loss)" }}>
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
