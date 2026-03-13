import clsx from "clsx";

export default function ValuePair({ label, value, tone = "default", emphasize = false }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-sm text-[color:var(--text-secondary)]">{label}</span>
      <span
        className={clsx(
          "numeric",
          emphasize ? "text-lg font-semibold" : "text-sm",
          tone === "profit" && "text-[color:var(--color-profit)]",
          tone === "loss" && "text-[color:var(--color-loss)]",
          tone === "default" && "text-[color:var(--text-primary)]",
        )}
      >
        {value}
      </span>
    </div>
  );
}
