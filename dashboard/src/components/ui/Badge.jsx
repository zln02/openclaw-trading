import clsx from "clsx";

const CLASS_STYLES = {
  profit: "bg-[color:var(--color-profit-bg)] text-[color:var(--color-profit)]",
  loss: "bg-[color:var(--color-loss-bg)] text-[color:var(--color-loss)]",
  neutral: "bg-[color:var(--color-neutral-bg)] text-[color:var(--text-secondary)]",
  info: "bg-[color:var(--color-info-bg)] text-[color:var(--color-info)]",
  warning: "bg-[color:var(--color-warning-bg)] text-[color:var(--color-warning)]",
  btc: "bg-[color:var(--color-btc-bg)] text-[color:var(--accent-btc)]",
  kr:  "bg-[color:var(--color-kr-bg)]  text-[color:var(--accent-kr)]",
  us:  "bg-[color:var(--color-us-bg)]  text-[color:var(--accent-us)]",
};

// /normalize: CSS variables instead of hard-coded hex
const INLINE_STYLES = {
  buy:     { background: "var(--color-profit-bg)", color: "var(--color-profit)" },
  sell:    { background: "var(--color-loss-bg)",   color: "var(--color-loss)" },
  hold:    { background: "var(--color-neutral-bg)", color: "var(--text-secondary)" },
  bullish: { background: "var(--color-profit-bg)", color: "var(--color-profit)" },
  bearish: { background: "var(--color-loss-bg)",   color: "var(--color-loss)" },
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
