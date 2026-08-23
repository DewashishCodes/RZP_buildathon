function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/**
 * A "meter" per the dataviz skill's figure contract: the fill (accent)
 * carries progress, the unfilled track is a muted step of the same
 * surface so state reads across the whole bar. One hue, not a
 * categorical color per root cause - the row label already carries
 * identity via text, so color here means "recovered vs remaining",
 * not "which root cause".
 */
export function ProgressRow({
  label,
  atRisk,
  recovered,
  rate,
}: {
  label: string;
  atRisk: number;
  recovered: number;
  rate: number;
}) {
  const pct = Math.max(0, Math.min(100, rate * 100));
  return (
    <div className="flex items-center gap-4 py-2.5">
      <div className="w-36 shrink-0 truncate text-sm text-text-secondary" title={label}>
        {label}
      </div>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full bg-accent transition-[width]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="w-20 shrink-0 text-right text-sm tabular-nums text-text-primary">{pct.toFixed(0)}%</div>
      <div className="hidden w-48 shrink-0 text-right text-xs tabular-nums text-text-muted sm:block">
        {formatRs(recovered)} / {formatRs(atRisk)}
      </div>
    </div>
  );
}
