import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export default function StatCard({ label, value, sub, trend, icon: Icon }) {
  const trendColor =
    trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-gray-500";
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;

  return (
    <div className="card flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-gray-600" />}
      </div>
      <div className="text-xl font-semibold tracking-tight">{value ?? "—"}</div>
      {sub != null && (
        <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
          <TrendIcon className="w-3 h-3" />
          <span>{sub}</span>
        </div>
      )}
    </div>
  );
}
