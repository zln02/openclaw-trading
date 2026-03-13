export function ErrorState({ message }) {
  return (
    <div className="rounded-[var(--panel-radius-sm)] border border-[color:var(--color-loss-bg)] bg-[color:var(--color-loss-bg)] px-4 py-3 text-sm text-[color:var(--color-loss)]">
      {message}
    </div>
  );
}

export function EmptyState({ message }) {
  return (
    <div className="rounded-[var(--panel-radius-sm)] border border-dashed border-white/10 px-4 py-10 text-center text-sm text-[color:var(--text-secondary)]">
      {message}
    </div>
  );
}
