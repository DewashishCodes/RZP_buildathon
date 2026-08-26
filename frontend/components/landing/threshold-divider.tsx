/**
 * A thin arch/doorway outline used as a section break instead of a plain
 * rule - the recurring visual echo of the threshold motif between major
 * sections. Duotone stroke (verdigris -> copper) via a gradient, matching
 * the page's two-accent color grammar. Purely decorative.
 */
export function ThresholdDivider() {
  return (
    <svg viewBox="0 0 400 48" fill="none" className="mx-auto h-8 w-full max-w-xs text-border-strong" aria-hidden="true">
      <defs>
        <linearGradient id="threshold-gradient" x1="0" y1="0" x2="400" y2="0">
          <stop offset="0%" stopColor="var(--verdigris)" stopOpacity="0.6" />
          <stop offset="50%" stopColor="var(--border-strong)" stopOpacity="0.5" />
          <stop offset="100%" stopColor="var(--copper)" stopOpacity="0.6" />
        </linearGradient>
      </defs>
      <path
        d="M4 46V22C4 11 20 2 200 2S396 11 396 22V46"
        stroke="url(#threshold-gradient)"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}
