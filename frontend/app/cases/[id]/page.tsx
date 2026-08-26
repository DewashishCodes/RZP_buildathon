import type { Metadata } from "next";
import Link from "next/link";
import { getCaseTimeline, type AuditEvent } from "@/lib/api";
import { EventTimeline } from "@/components/event-timeline";
import { StatusBadge } from "@/components/status-badge";
import { ArrowRightIcon, ChatIcon, ShieldIcon } from "@/components/icons";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  try {
    const { case: c } = await getCaseTimeline(id);
    const label = c.root_cause ?? c.type;
    return { title: `Case · ${label} — Janus` };
  } catch {
    return { title: "Case not found — Janus" };
  }
}

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

/**
 * The judge's first question about any case is "why did it do that?" - this
 * answers it up front from the audit trail that already exists (first
 * action_proposed rationale + its compliance verdict) instead of making
 * them scroll the timeline.
 */
function WhyThisAction({ events }: { events: AuditEvent[] }) {
  const proposed = events.find((e) => e.event_type === "action_proposed");
  const compliance = events.find((e) => e.event_type === "compliance_check");

  const action = proposed?.payload.action;
  const rationale = proposed?.payload.rationale;
  if (typeof rationale !== "string" || !rationale) return null;

  const substituted = compliance?.payload.substituted === true;
  const passed = compliance?.payload.passed === true;
  const reason = typeof compliance?.payload.reason === "string" ? compliance.payload.reason : undefined;

  return (
    <div className="rounded-xl border border-accent/30 bg-accent/5 p-5">
      <div className="flex items-center gap-2">
        <ChatIcon className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-semibold text-text-primary">Why this action?</h2>
      </div>
      {typeof action === "string" && (
        <p className="mt-2.5 text-sm text-text-primary">
          Agent proposed <span className="font-mono text-xs">{action}</span>
        </p>
      )}
      <p className="mt-1 text-sm leading-relaxed text-text-secondary">&ldquo;{rationale}&rdquo;</p>
      {compliance && (
        <div className="mt-3 flex items-start gap-2.5 border-t border-border pt-3">
          <ShieldIcon className={`mt-0.5 h-4 w-4 shrink-0 ${substituted ? "text-status-warning" : "text-status-good"}`} />
          <div className="text-xs">
            <span className={substituted ? "text-status-warning" : "text-status-good"}>
              {substituted ? "Guardrail rewrote it" : passed ? "Compliance check passed" : "Compliance check failed"}
            </span>
            {reason && (
              <>
                {" · "}
                <span className="text-text-muted">{reason}</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
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
  // Preserve the batch context so drilling into a case and coming back
  // doesn't land on the dashboard's "No batch selected" dead end.
  const dashboardHref = c.batch_id ? `/dashboard?batch=${c.batch_id}` : "/dashboard";

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-12">
      <div>
        <Link href={dashboardHref} className="text-sm text-text-muted hover:text-text-primary">
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

      <WhyThisAction events={events} />

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
        <h2 className="mb-4 text-lg font-medium text-text-primary">Timeline ({events.length + attempts.length})</h2>
        <EventTimeline events={events} attempts={attempts} />
      </section>

      <Link href={dashboardHref} className="inline-flex w-fit items-center gap-1.5 text-sm text-text-muted hover:text-text-primary">
        Back to dashboard
        <ArrowRightIcon className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
