import { NavLink, Outlet } from "react-router-dom";
import { Bitcoin, BarChart3, Globe, Activity } from "lucide-react";

const NAV = [
  { to: "/", icon: Bitcoin, label: "BTC" },
  { to: "/kr", icon: BarChart3, label: "KR 주식" },
  { to: "/us", icon: Globe, label: "US 주식" },
];

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-16 md:w-52 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
        <div className="flex items-center gap-2 px-4 py-4 border-b border-gray-800">
          <Activity className="w-6 h-6 text-emerald-400" />
          <span className="hidden md:inline font-bold text-sm tracking-wide">OpenClaw</span>
        </div>
        <nav className="flex-1 py-3 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors rounded-lg mx-2 ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                }`
              }
            >
              <Icon className="w-5 h-5 shrink-0" />
              <span className="hidden md:inline">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600 hidden md:block">
          v6.0 · 자동매매 대시보드
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-4 md:p-6">
        <Outlet />
      </main>
    </div>
  );
}
