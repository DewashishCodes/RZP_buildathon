import Link from "next/link";
import { ArrowRightIcon } from "@/components/icons";
import { Reveal } from "@/components/reveal";

export function FinalCta() {
  return (
    <Reveal className="flex flex-col items-center gap-4 text-center">
      <h2 className="font-display text-2xl text-landing-text">See it work end to end</h2>
      <div className="flex gap-3">
        <Link
          href="/run?demo=1"
          className="group inline-flex items-center gap-2 rounded-full bg-copper px-5 py-2.5 text-sm font-medium text-[#160f09] transition-all duration-150 ease-out hover:scale-[1.03] hover:bg-copper-bright hover:shadow-[0_0_24px_-6px_var(--copper)]"
        >
          Run demo batch
          <ArrowRightIcon className="h-3.5 w-3.5 transition-transform duration-150 ease-out group-hover:translate-x-0.5" />
        </Link>
        <Link
          href="/history"
          className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-text-primary transition-all duration-150 ease-out hover:scale-[1.03] hover:border-border-strong hover:bg-surface-1"
        >
          Browse history
        </Link>
      </div>
      <p className="font-numeric mt-4 text-[11px] text-text-muted">Janus — built for Razorpay Buildathon, Track 03.</p>
    </Reveal>
  );
}
