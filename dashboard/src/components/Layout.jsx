import { NavLink, Outlet } from "react-router-dom";
import { Bitcoin, BarChart3, Globe, Activity, Settings } from "lucide-react";

const NAV = [
  { to: "/", icon: Bitcoin, label: "BTC" },
  { to: "/kr", icon: BarChart3, label: "KR 주식" },
  { to: "/us", icon: Globe, label: "US 주식" },
];

export default function Layout() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header with Navigation */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="px-4 lg:px-6">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Activity className="w-6 h-6 text-accent" />
                <span className="font-bold text-lg tracking-tight text-text-primary">OpenClaw</span>
              </div>
              <span className="hidden sm:inline text-xs text-text-secondary ml-2">v6.0 · 자동매매 대시보드</span>
            </div>

            {/* Navigation Tabs */}
            <nav className="flex items-center gap-1">
              {NAV.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg transition-all duration-200 ${
                      isActive
                        ? "tab-active"
                        : "tab-inactive"
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{label}</span>
                </NavLink>
              ))}
            </nav>

            {/* Settings */}
            <div className="flex items-center">
              <button className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-card/50 transition-colors">
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-4 lg:p-6">
        <Outlet />
      </main>
    </div>
  );
}
