import { PlayIcon } from "@/components/icons";

/**
 * Placeholder slot for the pitch/demo video - swap the inner content for
 * a real <video>/embed once it exists. Kept as its own component so that
 * swap is a one-file change.
 */
export function DemoVideo() {
  return (
    <div className="mx-auto w-full max-w-3xl px-6">
      <div className="group relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl border border-dashed border-border-strong bg-surface-1">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.14]"
          style={{ background: "radial-gradient(ellipse at 30% 30%, var(--verdigris), transparent 55%), radial-gradient(ellipse at 70% 70%, var(--copper), transparent 55%)" }}
          aria-hidden="true"
        />
        <div className="relative flex flex-col items-center gap-3 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full border border-border-strong bg-surface-2 text-text-muted">
            <PlayIcon className="h-4 w-4 translate-x-0.5" />
          </span>
          <p className="font-numeric text-[11px] uppercase tracking-wider text-text-muted">Demo video — coming soon</p>
        </div>
      </div>
    </div>
  );
}
