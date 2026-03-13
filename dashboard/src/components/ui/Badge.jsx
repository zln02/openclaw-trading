import clsx from "clsx";

const CLASS_STYLES = {
  profit: "bg-[color:var(--color-profit-bg)] text-[color:var(--color-profit)]",
  loss: "bg-[color:var(--color-loss-bg)] text-[color:var(--color-loss)]",
  neutral: "bg-[color:var(--color-neutral-bg)] text-[color:var(--text-secondary)]",
  info: "bg-[color:var(--color-info-bg)] text-[color:var(--color-info)]",
  warning: "bg-[color:var(--color-warning-bg)] text-[color:var(--color-warning)]",
  btc: "bg-[rgba(247,147,26,0.12)] text-[color:var(--accent-btc)]",
  kr: "bg-[rgba(0,212,170,0.12)] text-[color:var(--accent-kr)]",
  us: "bg-[rgba(59,130,246,0.12)] text-[color:var(--accent-us)]",
};

const INLINE_STYLES = {
  buy: { background: "rgba(0,212,170,0.08)", color: "#00d4aa" },
  sell: { background: "rgba(255,71,87,0.08)", color: "#ff4757" },
  hold: { background: "rgba(255,255,255,0.08)", color: "#8b8b9e" },
  bullish: { background: "rgba(0,212,170,0.08)", color: "#00d4aa" },
  bearish: { background: "rgba(255,71,87,0.08)", color: "#ff4757" },
};

export default function Badge({ variant = "neutral", children, className = "" }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md px-2 py-1 numeric text-[11px] font-semibold leading-none",
        CLASS_STYLES[variant] || CLASS_STYLES.neutral,
        className,
      )}
      style={INLINE_STYLES[variant]}
    >
      {children}
    </span>
  );
}
