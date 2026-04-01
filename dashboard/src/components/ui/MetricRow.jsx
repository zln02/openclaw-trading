import clsx from "clsx";
import { getSignalColor } from "../../utils/signalColor";

// Re-export for backwards-compat (BtcPage imports this)
export { getSignalColor };

export default function MetricRow({
  label,
  value,
  valueLabel,
  progress,
  tone,
  compact = false,
  className = "",
}) {
  const normalized = Math.max(0, Math.min(100, progress ?? Number(value) ?? 0));
  const fill = tone || getSignalColor(normalized);

  return (
    <div className={clsx("space-y-2", className)}>
      <div className="flex items-center justify-between gap-4">
        <span className="text-xs uppercase tracking-[0.12em] text-[color:var(--text-secondary)]">
          {label}
        </span>
        <span className={clsx("numeric text-sm text-[color:var(--text-primary)]", compact && "text-xs")}>
          {valueLabel ?? value}
        </span>
      </div>

      {/* /optimize: transform:scaleX instead of width — composite layer only, no layout reflow */}
      {/* /harden:  role=progressbar + aria attrs for screen readers */}
      {/* /quieter: boxShadow glow removed */}
      <div className={clsx("overflow-hidden rounded-full bg-white/5", compact ? "h-1.5" : "h-2")}>
        <div
          role="progressbar"
          aria-valuenow={normalized}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
          className="h-full w-full origin-left rounded-full transition-transform duration-300"
          style={{
            backgroundColor: fill,
            transform: `scaleX(${normalized / 100})`,
          }}
        />
      </div>
    </div>
  );
}
