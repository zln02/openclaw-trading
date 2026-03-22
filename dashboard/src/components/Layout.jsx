import { Activity, Bot, Bitcoin, Landmark, Globe2, Sparkles } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import usePolling from "../hooks/usePolling";
import { getBtcComposite, getBtcPortfolio, getHealth, getStockPortfolio, getUsPositions, getUsFx } from "../api";
import HeroBanner from "./ui/HeroBanner";
import StatusBadge from "./ui/StatusBadge";
import { LangProvider, useLang } from "../hooks/useLang";

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

function LayoutInner() {
  const location = useLocation();
  const { lang, toggle, t } = useLang();
  const { data: btc } = usePolling(getBtcPortfolio, 30000);
  const { data: kr } = usePolling(getStockPortfolio, 30000);
  const { data: us } = usePolling(getUsPositions, 30000);
  const { data: fx } = usePolling(getUsFx, 60000);
  const { data: health, updatedAt } = usePolling(getHealth, 30000);
  const { data: composite } = usePolling(getBtcComposite, 30000);

  const fxRate = Number(fx?.rate || fx?.usdkrw || 1300);
  const btcAsset = (btc?.summary?.krw_balance || 0) + (btc?.summary?.total_eval || 0);
  const krAsset = kr?.estimated_asset || 0;
  const usAssetUsd = us?.summary?.total_current || 0;
  const usAssetKrw = Math.round(usAssetUsd * fxRate);
  const totalAsset = btcAsset + krAsset + usAssetKrw;

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
      value: usAssetUsd,
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
      <div className="bg-orb bg-orb-1" />
      <div className="bg-orb bg-orb-2" />
      <div className="bg-orb bg-orb-3" />
      <div className="dot-grid" />
      <div className="scanlines" />
      <div className="app-content">
        <header className="navbar-shell">
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
                  {t("OpenClaw Trading")}
                </div>
                <div className="subtle" style={{ fontSize: 13 }}>
                  {t("Dark ops dashboard for automated market execution")}
                </div>
              </div>
            </div>

            <nav className="nav-shell">
              {NAV.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} end={to === "/"}>
                  {({ isActive }) => (
                    <div className={`nav-tab ${isActive ? "is-active" : ""}`.trim()}>
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
              <button
                onClick={toggle}
                title={lang === "ko" ? "Switch to English" : "한국어로 전환"}
                style={{
                  background: "rgba(255,255,255,0.07)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 8,
                  padding: "4px 10px",
                  cursor: "pointer",
                  color: "var(--text-primary)",
                  fontSize: 13,
                  fontWeight: 700,
                  letterSpacing: "0.03em",
                }}
              >
                {lang === "ko" ? "EN" : "KO"}
              </button>
              <StatusBadge status={regime} />
              <div className="pill live-pill">
                <span className="live-dot" />
                <Sparkles size={14} />
                {t("Last update")} {formatTime(updatedAt)}
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

export default function Layout() {
  return (
    <LangProvider>
      <LayoutInner />
    </LangProvider>
  );
}
