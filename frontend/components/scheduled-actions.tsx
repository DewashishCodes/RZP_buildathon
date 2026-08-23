"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listScheduledCases, runDueJobs, type CaseSummary } from "@/lib/api";
import { ClockIcon, ArrowRightIcon } from "./icons";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/**
 * Proves the batch dashboard isn't secretly fast-forwarding every case:
 * lists cases genuinely waiting on a deferred round (from a non-instant
 * batch run) with their real next_action_at, and a button that does what
 * a cron/job queue would do on schedule - process every due case now.
 */
export function ScheduledActionsPanel({ merchantId }: { merchantId: string }) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listScheduledCases(merchantId)
      .then((data) => {
        if (!cancelled) setCases(data);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [merchantId, refreshKey]);

  async function handleProcessDue() {
    setProcessing(true);
    setLastResult(null);
    try {
      const result = await runDueJobs(merchantId);
      setLastResult(
        `Processed ${result.processed} case(s) — ${result.reached_terminal} reached a final state, ${result.rescheduled} rescheduled again.`,
      );
      setRefreshKey((k) => k + 1);
    } finally {
      setProcessing(false);
    }
  }

  if (loading) {
    return <div className="rounded-xl border border-border bg-surface-1 px-5 py-6 text-sm text-text-muted">Loading scheduled actions…</div>;
  }

  return (
    <div className="rounded-xl border border-border bg-surface-1 p-5">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <ClockIcon className="h-4 w-4 text-accent" />
          <h2 className="text-lg font-medium text-text-primary">Scheduled actions ({cases.length})</h2>
        </div>
        <button
          onClick={handleProcessDue}
          disabled={processing || cases.length === 0}
          className="inline-flex items-center gap-2 rounded-full border border-border-strong px-3.5 py-1.5 text-xs font-medium text-text-primary transition-colors hover:bg-surface-2 disabled:opacity-40"
        >
          {processing ? "Processing…" : "Process due jobs now"}
        </button>
      </div>
      <p className="mb-3 text-xs text-text-muted">
        Cases run with realistic scheduling mode sit here with a real next_action_at instead of
        resolving instantly. In production this is what a cron/job queue advances automatically;
        here it&apos;s a manual button so a demo doesn&apos;t have to wait.
      </p>

      {lastResult && (
        <div className="mb-3 rounded-lg border border-accent/30 bg-accent/10 px-3.5 py-2.5 text-xs text-text-secondary">
          {lastResult}
        </div>
      )}

      {cases.length === 0 ? (
        <div className="rounded-lg border border-border px-4 py-6 text-center text-xs text-text-muted">
          Nothing scheduled right now. Run a batch with &quot;Realistic scheduling mode&quot; on to populate this.
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-border">
          {cases.map((c) => (
            <div key={c.id} className="flex items-center justify-between gap-4 py-2.5 text-sm">
              <div className="flex items-center gap-3">
                <span className="rounded-md bg-surface-2 px-2 py-0.5 text-xs text-text-secondary">
                  {c.root_cause ?? "undiagnosed"}
                </span>
                <span className="tabular-nums text-text-primary">{formatRs(c.amount)}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-text-muted">
                  next action: {c.next_action_at ? new Date(c.next_action_at).toLocaleString() : "—"}
                </span>
                <Link href={`/cases/${c.id}`} className="inline-flex items-center gap-1 text-text-muted hover:text-text-primary">
                  <ArrowRightIcon className="h-3 w-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
