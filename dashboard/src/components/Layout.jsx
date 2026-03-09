import { Activity, Bot, Bitcoin, Landmark, Globe2, Sparkles } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import usePolling from "../hooks/usePolling";
import { getBtcComposite, getBtcPortfolio, getHealth, getStockPortfolio, getUsPositions } from "../api";
import HeroBanner from "./ui/HeroBanner";
import StatusBadge from "./ui/StatusBadge";

const NAV = [
  { to: "/", label: "BTC", icon: Bitcoin },
  { to: "/kr", label: "KR", icon: Landmark },
  { to: "/us", label: "US", icon: Globe2 },
  { to: "/agents", label: "Agents", icon: Bot },
];

const formatTime = (value) =>
  value
    ? new Intl.DateTimeFormat("ko-KR", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(value)
    : "--:--";

export default function Layout() {
  const location = useLocation();
  const { data: btc } = usePolling(getBtcPortfolio, 30000);
  const { data: kr } = usePolling(getStockPortfolio, 30000);
  const { data: us } = usePolling(getUsPositions, 30000);
  const { data: health, updatedAt } = usePolling(getHealth, 30000);
  const { data: composite } = usePolling(getBtcComposite, 30000);

  const btcAsset = (btc?.summary?.krw_balance || 0) + (btc?.summary?.total_eval || 0);
  const krAsset = kr?.estimated_asset || 0;
  const usAsset = us?.summary?.total_current || 0;
  const totalAsset = btcAsset + krAsset + usAsset;

  const metrics = {
    btc: {
      value: btcAsset,
      delta: Number(btc?.summary?.unrealized_pnl_pct || 0),
      prefix: "₩",
    },
    kr: {
      value: krAsset,
      delta: Number(kr?.cumulative_pnl_pct || 0),
      prefix: "₩",
    },
    us: {
      value: usAsset,
      delta: Number(us?.summary?.total_pnl_pct || 0),
      prefix: "$",
    },
    total: {
      value: totalAsset,
      delta:
        ((Number(btc?.summary?.unrealized_pnl_pct || 0) +
          Number(kr?.cumulative_pnl_pct || 0) +
          Number(us?.summary?.total_pnl_pct || 0)) /
          3) || 0,
      prefix: "₩",
    },
  };

  const regime =
    composite?.regime ||
    composite?.trend ||
    health?.regime ||
    "TRANSITION";

  return (
    <div className="app-shell">
      <div className="app-content">
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 20,
            padding: "18px 0 14px",
            backdropFilter: "blur(20px)",
            background: "rgba(10,10,15,0.78)",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div className="container" style={{ display: "flex", alignItems: "center", gap: 18, justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 16,
                  display: "grid",
                  placeItems: "center",
                  background: "var(--gradient-main)",
                  boxShadow: "0 18px 44px rgba(139,92,246,0.35)",
                }}
              >
                <Activity size={22} />
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.04em" }}>
                  OpenClaw Trading
                </div>
                <div className="subtle" style={{ fontSize: 13 }}>
                  Dark ops dashboard for automated market execution
                </div>
              </div>
            </div>

            <nav
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: 6,
                borderRadius: 999,
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              {NAV.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} end={to === "/"}>
                  {({ isActive }) => (
                    <div
                      style={{
                        position: "relative",
                        padding: "10px 16px",
                        borderRadius: 999,
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                        background: isActive ? "rgba(255,255,255,0.06)" : "transparent",
                      }}
                    >
                      <Icon size={16} />
                      <span style={{ fontWeight: 700 }}>{label}</span>
                      {isActive ? (
                        <span
                          className="nav-indicator"
                          style={{
                            position: "absolute",
                            left: 14,
                            right: 14,
                            bottom: 2,
                            height: 3,
                            borderRadius: 999,
                            background: "var(--gradient-main)",
                          }}
                        />
                      ) : null}
                    </div>
                  )}
                </NavLink>
              ))}
            </nav>

            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <StatusBadge status={regime} />
              <div className="pill">
                <Sparkles size={14} />
                Last update {formatTime(updatedAt)}
              </div>
            </div>
          </div>
        </header>

        <main style={{ padding: "24px 0 40px" }}>
          <div className="container">
            <HeroBanner metrics={metrics} />
            <Outlet context={{ currentPath: location.pathname, regime, updatedAt }} />
          </div>
        </main>
      </div>
    </div>
  );
}
