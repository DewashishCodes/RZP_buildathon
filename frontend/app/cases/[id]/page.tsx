import Link from "next/link";
import { getCaseTimeline } from "@/lib/api";
import { EventTimeline } from "@/components/event-timeline";
import { StatusBadge } from "@/components/status-badge";
import { ArrowRightIcon, PhoneIcon } from "@/components/icons";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export default async function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let timeline;
  try {
    timeline = await getCaseTimeline(id);
  } catch {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-text-secondary">Case not found.</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm text-text-muted hover:text-text-primary">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  const { case: c, events, attempts } = timeline;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-12">
      <div>
        <Link href="/dashboard" className="text-sm text-text-muted hover:text-text-primary">
          ← Back to dashboard
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
            {c.type} · {c.root_cause ?? "undiagnosed"}
          </h1>
          <StatusBadge status={c.status} />
        </div>
        <p className="mt-1 font-mono text-xs text-text-muted">{c.id}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="text-xs text-text-muted">Amount</div>
          <div className="mt-1 text-lg font-semibold text-text-primary">{formatRs(c.amount)}</div>
        </div>
        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="text-xs text-text-muted">Outcome</div>
          <div className="mt-1 text-lg font-semibold text-text-primary">{c.outcome}</div>
        </div>
        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="text-xs text-text-muted">Recovered</div>
          <div className="mt-1 text-lg font-semibold text-status-good">{formatRs(c.recovered_amount)}</div>
        </div>
        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="text-xs text-text-muted">Disputed</div>
          <div className="mt-1 text-lg font-semibold text-text-primary">{c.disputed ? "Yes" : "No"}</div>
        </div>
      </div>

      {c.raw_failure_reason && (
        <div className="rounded-lg border border-border bg-surface-1 px-4 py-3 text-sm text-text-secondary">
          <span className="text-text-muted">Raw failure reason: </span>
          {c.raw_failure_reason}
        </div>
      )}

      <section>
        <h2 className="mb-4 text-lg font-medium text-text-primary">Timeline ({events.length} events)</h2>
        <EventTimeline events={events} />
      </section>

      {attempts.length > 0 && (
        <section>
          <h2 className="mb-4 text-lg font-medium text-text-primary">Attempts ({attempts.length})</h2>
          <div className="flex flex-col gap-3">
            {attempts.map((a) => (
              <div key={a.id} className="rounded-lg border border-border bg-surface-1 px-4 py-3">
                <div className="flex items-baseline justify-between gap-4 text-sm">
                  <span className="font-medium text-text-primary">
                    {a.action} via {a.channel}
                  </span>
                  <span className="text-xs text-text-muted">{new Date(a.timestamp).toLocaleString()}</span>
                </div>
                <div className="mt-1 text-sm text-text-secondary">
                  outcome: <span className="text-text-primary">{a.outcome}</span>
                  {a.promise_to_pay_date && <> · promised: {a.promise_to_pay_date}</>}
                </div>
                {a.transcript && (
                  <details className="mt-3 group">
                    <summary className="flex cursor-pointer items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary">
                      <PhoneIcon className="h-3 w-3" />
                      View call transcript
                    </summary>
                    <pre className="mt-2 whitespace-pre-wrap rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-xs leading-relaxed text-text-secondary">
                      {a.transcript}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <Link href="/dashboard" className="inline-flex w-fit items-center gap-1.5 text-sm text-text-muted hover:text-text-primary">
        Back to dashboard
        <ArrowRightIcon className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
