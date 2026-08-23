import Link from "next/link";
import { getCaseTimeline, type AuditEvent } from "@/lib/api";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

const EVENT_COLORS: Record<string, string> = {
  detected: "border-neutral-700",
  diagnosed: "border-neutral-700",
  action_proposed: "border-blue-700",
  compliance_check: "border-purple-700",
  action_executed: "border-neutral-700",
  outcome_recorded: "border-neutral-700",
  stopped: "border-red-700",
  escalated: "border-amber-700",
};

function EventCard({ event }: { event: AuditEvent }) {
  const border = EVENT_COLORS[event.event_type] ?? "border-neutral-700";
  return (
    <div className={`rounded-md border-l-4 ${border} bg-neutral-900 px-4 py-3`}>
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-mono text-sm font-medium">{event.event_type}</span>
        <span className="text-xs text-neutral-500">
          {event.actor} · {new Date(event.timestamp).toLocaleString()}
        </span>
      </div>
      <pre className="mt-2 overflow-x-auto text-xs text-neutral-400">
        {JSON.stringify(event.payload, null, 2)}
      </pre>
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
        <p className="text-neutral-400">Case not found.</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm text-neutral-400 hover:text-white">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  const { case: c, events, attempts } = timeline;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-16">
      <div>
        <Link href="/dashboard" className="text-sm text-neutral-400 hover:text-white">
          ← Back to dashboard
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {c.type} · {c.root_cause ?? "undiagnosed"}
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          <code>{c.id}</code>
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-neutral-800 p-4">
          <div className="text-xs text-neutral-500">Amount</div>
          <div className="mt-1 text-lg font-semibold">{formatRs(c.amount)}</div>
        </div>
        <div className="rounded-lg border border-neutral-800 p-4">
          <div className="text-xs text-neutral-500">Status</div>
          <div className="mt-1 text-lg font-semibold">{c.status}</div>
        </div>
        <div className="rounded-lg border border-neutral-800 p-4">
          <div className="text-xs text-neutral-500">Outcome</div>
          <div className="mt-1 text-lg font-semibold">{c.outcome}</div>
        </div>
        <div className="rounded-lg border border-neutral-800 p-4">
          <div className="text-xs text-neutral-500">Recovered</div>
          <div className="mt-1 text-lg font-semibold text-emerald-400">{formatRs(c.recovered_amount)}</div>
        </div>
      </div>

      {c.raw_failure_reason && (
        <div className="rounded-md border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-400">
          <span className="text-neutral-500">Raw failure reason: </span>
          {c.raw_failure_reason}
        </div>
      )}

      <section>
        <h2 className="mb-3 text-lg font-medium">Timeline ({events.length} events)</h2>
        <div className="flex flex-col gap-2">
          {events.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </div>
      </section>

      {attempts.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-medium">Attempts ({attempts.length})</h2>
          <div className="flex flex-col gap-3">
            {attempts.map((a) => (
              <div key={a.id} className="rounded-md border border-neutral-800 bg-neutral-900 px-4 py-3">
                <div className="flex items-baseline justify-between gap-4 text-sm">
                  <span className="font-medium">
                    {a.action} via {a.channel}
                  </span>
                  <span className="text-xs text-neutral-500">{new Date(a.timestamp).toLocaleString()}</span>
                </div>
                <div className="mt-1 text-sm text-neutral-400">
                  outcome: <span className="text-neutral-200">{a.outcome}</span>
                  {a.promise_to_pay_date && <> · promised: {a.promise_to_pay_date}</>}
                </div>
                {a.transcript && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-neutral-500 hover:text-neutral-300">
                      View call transcript
                    </summary>
                    <pre className="mt-2 whitespace-pre-wrap rounded bg-neutral-950 px-3 py-2 text-xs text-neutral-300">
                      {a.transcript}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
