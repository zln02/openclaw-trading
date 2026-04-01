import { motion } from "framer-motion";
import clsx from "clsx";
import { cardVariants } from "./motion";

export default function Card({
  title,
  icon,
  action,
  children,
  className = "",
  bodyClassName = "",
  accent = false,
  delay = 0,
}) {
  return (
    <motion.section
      custom={delay}
      initial="hidden"
      animate="visible"
      variants={cardVariants}
      aria-label={title || undefined}
      className={clsx(
        "group relative overflow-hidden rounded-[var(--panel-radius)] border border-[color:var(--border-subtle)] bg-[linear-gradient(180deg,rgba(18,18,26,0.94),rgba(9,11,17,0.98))] shadow-[var(--shadow-panel)]",
        "before:pointer-events-none before:absolute before:inset-0 before:bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.03),transparent_40%)]",
        accent && "ring-1 ring-white/5",
        className,
      )}
    >
      {(title || icon || action) && (
        <div className="relative z-[1] flex items-center gap-2 border-b border-[color:var(--border-subtle)] px-4 py-3">
          {icon ? <span className="text-[color:var(--text-secondary)]">{icon}</span> : null}
          {/* /harden: h3 for proper heading hierarchy (screen reader navigation) */}
          {title ? (
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
              {title}
            </h3>
          ) : null}
          {action ? <div className="ml-auto">{action}</div> : null}
        </div>
      )}
      <div className={clsx("relative z-[1] p-4", bodyClassName)}>{children}</div>
    </motion.section>
  );
}
