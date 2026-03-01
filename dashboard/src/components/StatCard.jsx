import PropTypes from "prop-types";
import { TrendingUp, TrendingDown, Minus, Info } from "lucide-react";

export default function StatCard({ 
  label, 
  value, 
  sub, 
  trend, 
  icon: Icon, 
  size = "default",
  tooltip 
}) {
  const trendColor =
    trend === "up" ? "text-profit" : trend === "down" ? "text-loss" : trend === "warning" ? "text-yellow-400" : "text-text-secondary";
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;

  const sizeClasses = {
    compact: "p-3",
    default: "p-4",
    large: "p-5"
  };

  const valueSizeClasses = {
    compact: "text-lg",
    default: "text-xl",
    large: "text-2xl"
  };

  return (
    <div className={`card ${sizeClasses[size]} relative group`}>
      {tooltip && (
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="relative">
            <Info className="w-3 h-3 text-text-secondary cursor-help" />
            <div className="absolute bottom-full right-0 mb-2 w-48 p-2 bg-card border border-border rounded-lg text-xs text-text-secondary whitespace-normal z-10 hidden group-hover:block">
              {tooltip}
            </div>
          </div>
        </div>
      )}
      
      <div className="flex items-start justify-between mb-2">
        <span className="data-label">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-text-secondary" />}
      </div>
      
      <div className={`data-value ${valueSizeClasses[size]} mb-1`}>
        {value ?? "—"}
      </div>
      
      {sub != null && (
        <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
          <TrendIcon className="w-3 h-3" />
          <span className="font-medium">{sub}</span>
        </div>
      )}
    </div>
  );
}

StatCard.propTypes = {
  label: PropTypes.string,
  value: PropTypes.node,
  sub: PropTypes.node,
  trend: PropTypes.oneOf(["up", "down", "neutral", "warning"]),
  icon: PropTypes.elementType,
  size: PropTypes.oneOf(["compact", "default", "large"]),
  tooltip: PropTypes.string,
};
