export function StatTile({
  label,
  value,
  accent,
  hint,
}: {
  label: string;
  value: string;
  accent?: "good" | "accent" | "warning" | "critical" | "none";
  hint?: string;
}) {
  const accentClass =
    accent === "good"
      ? "text-status-good"
      : accent === "accent"
        ? "text-accent"
        : accent === "warning"
          ? "text-status-warning"
          : accent === "critical"
            ? "text-status-critical"
            : "text-text-primary";

  return (
    <div className="rounded-xl border border-border bg-surface-1 p-5">
      <div className="text-xs font-medium uppercase tracking-wide text-text-muted">{label}</div>
      <div className={`mt-2 text-[28px] font-semibold leading-none ${accentClass}`}>{value}</div>
      {hint && <div className="mt-2 text-xs text-text-muted">{hint}</div>}
    </div>
  );
}
