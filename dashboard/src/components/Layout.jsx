import { AnimatePresence, motion } from "framer-motion";
import { Activity, Bot, Bitcoin, Globe2, Landmark, Settings2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation, useOutlet } from "react-router-dom";
import {
  getBtcPortfolio,
  getHealth,
  getStockPortfolio,
  getUsPositions,
} from "../api";
import usePolling from "../hooks/usePolling";
import { krw, pct, relativeTime, usd } from "../lib/format";
import { pageVariants } from "./ui/motion";

const NAV = [
  { to: "/", label: "BTC", accent: "var(--accent-btc)", icon: Bitcoin },
  { to: "/kr", label: "KR", accent: "var(--accent-kr)", icon: Landmark },
  { to: "/us", label: "US", accent: "var(--accent-us)", icon: Globe2 },
  { to: "/agents", label: "Agents", accent: "var(--accent-agents)", icon: Bot },
];

function metricTone(value) {
  return Number(value || 0) >= 0 ? "text-[color:var(--color-profit)]" : "text-[color:var(--color-loss)]";
}

function formatHealthIssues(health) {
  const components = health?.components || {};
  const issues = Object.entries(components)
    .filter(([, value]) => value?.status !== "healthy")
    .map(([name, value]) => `${name}: ${value?.error || value?.details?.error || value?.status || "degraded"}`);

  if (issues.length > 0) {
    return issues.join(", ");
  }

  const slow = Object.entries(components)
    .filter(([, value]) => value?.status === "healthy" && Number(value?.latency_ms || 0) >= 1000)
    .map(([name, value]) => `${name}: slow response (${value.latency_ms}ms)`);

  return slow.join(", ");
}

function SummaryCell({ label, value, delta, accent }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 border-b border-white/5 px-4 py-2 md:border-b-0 md:border-r md:border-white/5">
      <div className="min-w-0">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
          {label}
        </div>
        <div className="mt-1 truncate numeric text-base font-semibold text-[color:var(--text-primary)]">
          {value}
        </div>
      </div>
      <div className={`shrink-0 numeric text-sm font-semibold ${metricTone(delta)}`}>
        {pct(delta)}
      </div>
    </div>
  );
}

export default function Layout() {
  const location = useLocation();
  const outlet = useOutlet();
  const [now, setNow] = useState(Date.now());

  const { data: btc } = usePolling(getBtcPortfolio, 30000);
  const { data: kr } = usePolling(getStockPortfolio, 30000);
  const { data: us } = usePolling(getUsPositions, 30000);
  const { data: health, updatedAt } = usePolling(getHealth, 30000);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  const summary = useMemo(() => {
    const btcAsset = Number(btc?.summary?.estimated_asset || 0);
    const krAsset = Number(kr?.estimated_asset || 0);
    const usAsset = Number(us?.summary?.total_current || 0);
    const totalAsset = btcAsset + krAsset + usAsset;

    return [
      {
        label: "Global Portfolio",
        value: krw(totalAsset),
        delta:
          ((Number(btc?.summary?.unrealized_pnl_pct || 0) +
            Number(kr?.cumulative_pnl_pct || 0) +
            Number(us?.summary?.total_pnl_pct || 0)) /
            3) || 0,
        accent: "var(--text-primary)",
      },
      {
        label: "BTC Assets",
        value: krw(btcAsset),
        delta: Number(btc?.summary?.unrealized_pnl_pct || 0),
        accent: "var(--accent-btc)",
      },
      {
        label: "KR Assets",
        value: krw(krAsset),
        delta: Number(kr?.cumulative_pnl_pct || 0),
        accent: "var(--accent-kr)",
      },
      {
        label: "US Assets",
        value: usd(usAsset),
        delta: Number(us?.summary?.total_pnl_pct || 0),
        accent: "var(--accent-us)",
      },
    ];
  }, [btc, kr, us]);

  const healthTone = health?.status === "ok" ? "var(--color-profit)" : "var(--color-loss)";
  const healthTooltip = formatHealthIssues(health);
  const clock = new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(now);

  return (
    <div className="min-h-screen bg-[color:var(--bg-primary)] text-[color:var(--text-primary)]">
      <header className="sticky top-0 z-40 border-b border-[color:var(--border-subtle)] bg-[rgba(10,10,15,0.92)] backdrop-blur-xl">
        <div className="mx-auto flex h-[var(--topbar-height)] w-full max-w-[1600px] items-center justify-between gap-4 px-3 lg:px-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl border border-white/10 bg-[linear-gradient(135deg,rgba(247,147,26,0.25),rgba(59,130,246,0.22))]">
              <Activity size={18} />
            </div>
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-[color:var(--text-muted)]">
                OpenClaw
              </div>
              <div className="text-base font-semibold text-[color:var(--text-primary)]">
                Trading Terminal
              </div>
            </div>
          </div>

          <nav className="hidden items-center gap-1 rounded-full border border-white/10 bg-white/[0.02] p-1 md:flex">
            {NAV.map(({ to, label, accent, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === "/"}>
                {({ isActive }) => (
                  <div className="relative flex min-w-[86px] items-center justify-center gap-2 rounded-full px-4 py-2 text-sm">
                    <span className="relative z-10 h-2 w-2 rounded-full" style={{ background: accent }} />
                    <Icon size={15} className={`relative z-10 ${isActive ? "text-white" : "text-[color:var(--text-muted)]"}`} />
                    <span className={`relative z-10 ${isActive ? "text-white" : "text-[color:var(--text-muted)]"}`}>{label}</span>
                    {isActive ? (
                      <motion.span
                        layoutId="active-terminal-tab"
                        className="absolute inset-0 z-0 rounded-full bg-white/[0.06]"
                        style={{ boxShadow: `inset 0 0 0 1px ${accent}` }}
                      />
                    ) : null}
                    {isActive ? (
                      <motion.span
                        layoutId="active-terminal-underline"
                        className="absolute bottom-0 left-3 right-3 z-0 h-0.5 rounded-full"
                        style={{ background: accent }}
                      />
                    ) : null}
                  </div>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2 md:gap-3">
            <div className="group relative hidden md:block">
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-[color:var(--text-secondary)]">
                <span className="h-2 w-2 rounded-full" style={{ background: healthTone }} />
                <span>System {health?.status || "checking"}</span>
              </div>
              {health?.status === "degraded" && healthTooltip ? (
                <div className="pointer-events-none absolute right-0 top-full z-20 mt-2 hidden w-72 rounded-xl border border-white/10 bg-[rgba(12,14,20,0.96)] px-3 py-2 text-xs text-[color:var(--text-secondary)] shadow-[var(--shadow-panel)] group-hover:block">
                  {healthTooltip}
                </div>
              ) : null}
            </div>
            <div className="hidden rounded-full border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-[color:var(--text-secondary)] md:block">
              Last update <span className="numeric">{relativeTime(updatedAt, now)}</span>
            </div>
            <div className="rounded-full border border-white/10 bg-white/[0.02] px-3 py-2 numeric text-xs text-[color:var(--text-secondary)]">
              {clock}
            </div>
            <button
              type="button"
              className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/[0.02] text-[color:var(--text-secondary)]"
            >
              <Settings2 size={15} />
            </button>
          </div>
        </div>
      </header>

      <section className="border-b border-[color:var(--border-subtle)] bg-[color:var(--bg-strip)]">
        <div className="mx-auto grid w-full max-w-[1600px] md:grid-cols-4" style={{ minHeight: "var(--summary-height)" }}>
          {summary.map((item) => (
            <SummaryCell key={item.label} {...item} />
          ))}
        </div>
      </section>

      <main className="mx-auto w-full max-w-[1600px] px-3 pb-4 pt-3 lg:px-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {outlet}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
