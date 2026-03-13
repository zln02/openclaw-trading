export default function LoadingSkeleton({ height = 180, className = "" }) {
  return (
    <div
      className={`animate-pulse rounded-[var(--panel-radius-sm)] border border-white/5 bg-white/[0.03] ${className}`.trim()}
      style={{ height }}
    />
  );
}
