import Link from "next/link";
import { ArrowRightIcon } from "@/components/icons";

/**
 * Two soft glows - verdigris left, copper right - meet at a seam behind
 * the centered wordmark: standing in the doorway, different light on
 * each side. This is the hero's instance of the two-faces motif; it's
 * not a decorative gradient-mesh background, it's motivated by where the
 * wordmark sits relative to the two fields of light.
 */
export function Hero() {
  return (
    <div className="relative overflow-hidden">
      <div
        className="pointer-events-none absolute top-0 left-0 h-full w-1/2 opacity-[0.16]"
        style={{ background: "radial-gradient(ellipse at 80% 20%, var(--verdigris), transparent 60%)" }}
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute top-0 right-0 h-full w-1/2 opacity-[0.16]"
        style={{ background: "radial-gradient(ellipse at 20% 20%, var(--copper), transparent 60%)" }}
        aria-hidden="true"
      />

      <div className="relative mx-auto flex max-w-3xl flex-col items-center gap-6 px-6 py-24 text-center">
        <span className="font-numeric w-fit rounded-full border border-border bg-surface-1 px-3 py-1 text-[11px] uppercase tracking-wider text-text-secondary">
          Razorpay Buildathon · Track 03
        </span>

        <h1 className="font-display text-6xl leading-none font-semibold text-landing-text sm:text-7xl">Janus</h1>
        <p className="text-sm text-text-muted">AI Revenue Recovery Agent</p>

        <p className="max-w-xl text-base leading-relaxed text-text-secondary">
          Named for the god who watches both directions of a threshold at once: Janus detects
          revenue at risk, diagnoses root cause, and proposes a bounded recovery action - but a
          separate, deterministic layer decides whether that action ever crosses into execution.
        </p>

        <div className="mt-2 flex gap-3">
          <Link
            href="/run?demo=1"
            className="group inline-flex items-center gap-2 rounded-full bg-copper px-5 py-2.5 text-sm font-medium text-[#160f09] transition-all duration-150 ease-out hover:scale-[1.03] hover:bg-copper-bright hover:shadow-[0_0_24px_-6px_var(--copper)]"
          >
            Run demo batch
            <ArrowRightIcon className="h-3.5 w-3.5 transition-transform duration-150 ease-out group-hover:translate-x-0.5" />
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-text-primary transition-all duration-150 ease-out hover:scale-[1.03] hover:border-border-strong hover:bg-surface-1"
          >
            View dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
