import { MailIcon, XCircleIcon } from "@/components/icons";
import { Reveal } from "@/components/reveal";

/**
 * One card cut by a seam rather than two separate cards - the two leak
 * types as literally two faces of the same coverage claim, echoing the
 * hero's two-light-fields treatment at a smaller scale.
 */
export function Breadth() {
  return (
    <Reveal>
      <div className="relative grid overflow-hidden rounded-lg border border-border bg-surface-1 sm:grid-cols-2">
        <div
          className="pointer-events-none absolute top-0 bottom-0 left-1/2 hidden w-px -translate-x-1/2 sm:block"
          style={{ background: "linear-gradient(to bottom, var(--verdigris-border), var(--copper-border))" }}
          aria-hidden="true"
        />
        <div className="flex flex-col gap-2 p-6">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-verdigris-fill text-verdigris-bright">
              <XCircleIcon className="h-4 w-4" />
            </span>
            <h3 className="text-sm font-semibold text-text-primary">Payment &amp; mandate failures</h3>
          </div>
          <p className="text-xs leading-relaxed text-text-muted">
            Failed card/UPI debits and revoked subscription mandates, root-caused down to
            insufficient funds, expired cards, issuer declines, bank timeouts, and fraud.
          </p>
        </div>
        <div className="flex flex-col gap-2 border-t border-border p-6 sm:border-t-0 sm:border-l">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-copper-fill text-copper-bright">
              <MailIcon className="h-4 w-4" />
            </span>
            <h3 className="text-sm font-semibold text-text-primary">B2B receivables</h3>
          </div>
          <p className="text-xs leading-relaxed text-text-muted">
            Overdue invoices bucketed by how late they are, with disputes routed straight to
            human escalation instead of an automated nudge.
          </p>
        </div>
      </div>
    </Reveal>
  );
}
