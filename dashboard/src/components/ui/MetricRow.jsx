import clsx from "clsx";

export function getSignalColor(value) {
  if (value <= 30) return "#ff4757";
  if (value <= 70) return "#ffa502";
  return "#00d4aa";
}

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
        <span
          className={clsx(
            "numeric text-sm text-[color:var(--text-primary)]",
            compact && "text-xs",
          )}
        >
          {valueLabel ?? value}
        </span>
      </div>
      <div className={clsx("overflow-hidden rounded-full bg-white/5", compact ? "h-1.5" : "h-2")}>
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{
            width: `${normalized}%`,
            backgroundColor: fill,
            boxShadow: normalized > 0 ? `0 0 12px ${fill}66` : "none",
          }}
        />
      </div>
    </div>
  );
}
