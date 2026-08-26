import Link from "next/link";
import { listBatches, type BatchListItem } from "@/lib/api";
import { ArrowRightIcon } from "@/components/icons";
import { CountUp } from "@/components/count-up";
import { Reveal } from "@/components/reveal";

function shortId(id: string) {
  return id.slice(0, 8);
}

async function getLatestBatch(): Promise<BatchListItem | null> {
  try {
    const batches = await listBatches();
    return batches[0] ?? null;
  } catch {
    // Backend unreachable (e.g. a fresh clone with nothing running yet) -
    // degrade to the same empty-state CTA as "no batches yet" rather than
    // hard-failing the page.
    return null;
  }
}

/**
 * ₹ at risk uses verdigris (the retrospective face - what's wrong, not
 * yet acted on), ₹ recovered uses copper (the prospective face - the
 * guardrail-approved outcome). Recovery rate, being the ratio of the
 * two, sits in the warm off-white - it's not itself one face or the
 * other.
 */
export async function ProofStrip() {
  const batch = await getLatestBatch();

  if (!batch) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="w-full max-w-lg rounded-lg border border-border bg-surface-1 px-6 py-10">
          <p className="text-sm text-text-secondary">
            No batch has run yet on this instance - these numbers populate the moment one does.
          </p>
          <Link
            href="/run?demo=1"
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-copper px-5 py-2.5 text-sm font-medium text-[#160f09] transition-colors hover:bg-copper-bright"
          >
            Run the demo batch
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </Link>
        </div>
        <p className="max-w-md text-xs leading-relaxed text-text-muted">
          Every number on this page is a real run of the actual pipeline against a simulated
          payments/receivables environment with a hidden recoverability model - not live
          production transactions.
        </p>
      </div>
    );
  }

  return (
    <Reveal className="flex flex-col items-center gap-6 text-center">
      <div className="grid w-full max-w-2xl grid-cols-1 gap-6 sm:grid-cols-3">
        <div>
          <div className="font-numeric text-[11px] uppercase tracking-wider text-verdigris-bright">₹ at risk</div>
          <div className="font-numeric mt-2 text-4xl font-medium text-landing-text">
            <CountUp value={batch.total_at_risk} prefix="₹" />
          </div>
        </div>
        <div>
          <div className="font-numeric text-[11px] uppercase tracking-wider text-copper-bright">₹ recovered</div>
          <div className="font-numeric mt-2 text-4xl font-medium text-landing-text">
            <CountUp value={batch.total_recovered} prefix="₹" />
          </div>
        </div>
        <div>
          <div className="font-numeric text-[11px] uppercase tracking-wider text-text-muted">Recovery rate</div>
          <div className="font-numeric mt-2 text-4xl font-medium text-landing-text">
            <CountUp value={batch.recovery_rate * 100} suffix="%" decimals={1} />
          </div>
        </div>
      </div>
      <Link
        href={`/dashboard?batch=${batch.batch_id}`}
        className="font-numeric inline-flex items-center gap-1.5 text-xs text-text-muted transition-colors hover:text-text-secondary"
      >
        batch <span className="text-text-secondary">{shortId(batch.batch_id)}</span> · {batch.total_cases} cases ·
        view dashboard
        <ArrowRightIcon className="h-3 w-3" />
      </Link>
      <p className="max-w-md text-xs leading-relaxed text-text-muted">
        Real pipeline output, not a mockup - but against a simulated payments/receivables
        environment with a hidden recoverability model, not live production transactions.
      </p>
    </Reveal>
  );
}
