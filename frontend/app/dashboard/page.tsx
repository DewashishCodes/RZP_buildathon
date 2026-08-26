"use client";

import { Suspense, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getBatchSummary, listCases, type BatchSummary, type CaseSummary } from "@/lib/api";
import { StatTile } from "@/components/stat-tile";
import { ProgressRow } from "@/components/progress-row";
import { StatusBadge } from "@/components/status-badge";
import { ScheduledActionsPanel } from "@/components/scheduled-actions";
import { GuardrailFeed } from "@/components/guardrail-feed";
import { RecoveryChart } from "@/components/recovery-chart";
import { RecentBatches } from "@/components/recent-batches";
import { useMerchant } from "@/components/merchant-context";
import { ArrowRightIcon, ShieldIcon, SwapIcon } from "@/components/icons";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

interface LoadState {
  summary: BatchSummary | null;
  cases: CaseSummary[];
  error: string | null;
}

function useBatchData(batchId: string): LoadState {
  const [state, setState] = useState<LoadState>({ summary: null, cases: [], error: null });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    // Polls while the batch still has work in flight (open/recovering
    // cases) so a background run's ticking numbers show up here without a
    // manual refresh; stops once everything is terminal.
    async function load() {
      try {
        const [summary, cases] = await Promise.all([getBatchSummary(batchId), listCases({ batchId })]);
        if (!cancelled) setState({ summary, cases, error: null });
        if (!cancelled && cases.some((c) => c.status === "open" || c.status === "recovering")) {
          timer = setTimeout(load, 4000);
        }
      } catch (err) {
        if (!cancelled) setState({ summary: null, cases: [], error: err instanceof Error ? err.message : "Failed to load batch" });
      }
    }

    load();
    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
    };
  }, [batchId]);

  return state;
}

// Keyed by batchId so switching batches remounts this with fresh state
// (statusFilter included) instead of needing manual reset effects.
function BatchDashboard({ batchId }: { batchId: string }) {
  const { summary, cases, error } = useBatchData(batchId);
  const { merchantId } = useMerchant();
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const visibleCases = useMemo(
    () => (statusFilter ? cases.filter((c) => c.status === statusFilter) : cases),
    [cases, statusFilter],
  );

  const rootCauseRows = useMemo(() => {
    if (!summary) return [];
    return Object.entries(summary.by_root_cause).sort((a, b) => b[1].at_risk - a[1].at_risk);
  }, [summary]);

  if (error) {
    return (
      <div className="mx-auto max-w-xl px-6 py-16">
        <div className="rounded-lg border border-status-critical/30 bg-status-critical-bg px-4 py-3 text-sm text-status-critical">
          {error}
        </div>
      </div>
    );
  }

  if (!summary) {
    return <div className="mx-auto max-w-6xl px-6 py-24 text-sm text-text-muted">Loading batch…</div>;
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Batch summary</h1>
        <p className="mt-1 font-mono text-xs text-text-muted">{summary.batch_id}</p>
      </div>

      {merchantId && <RecentBatches merchantId={merchantId} currentBatchId={batchId} />}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="₹ at risk" value={formatRs(summary.total_at_risk)} />
        <StatTile label="₹ recovered" value={formatRs(summary.total_recovered)} accent="good" />
        <StatTile label="Recovery rate" value={`${(summary.recovery_rate * 100).toFixed(1)}%`} accent="good" />
        <StatTile label="Cases" value={String(summary.total_cases)} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex items-center gap-4 rounded-xl border border-border bg-surface-1 p-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-status-warning-bg text-status-warning">
            <ShieldIcon className="h-5 w-5" />
          </span>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-text-muted">Stopping-rule triggers</div>
            <div className="mt-0.5 text-xl font-semibold text-text-primary">{summary.stopping_rule_triggers}</div>
            <div className="text-xs text-text-muted">proof guardrails fired, not just existed</div>
          </div>
        </div>
        <div className="flex items-center gap-4 rounded-xl border border-border bg-surface-1 p-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
            <SwapIcon className="h-5 w-5" />
          </span>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-text-muted">Compliance substitutions</div>
            <div className="mt-0.5 text-xl font-semibold text-text-primary">{summary.compliance_substitutions}</div>
            <div className="text-xs text-text-muted">proof compliance changed behavior</div>
          </div>
        </div>
      </div>

      {merchantId && <ScheduledActionsPanel key={merchantId} merchantId={merchantId} />}

      <RecoveryChart batchId={batchId} />

      <GuardrailFeed batchId={batchId} />

      <section>
        <h2 className="mb-1 text-lg font-medium text-text-primary">Recovery by root cause</h2>
        <p className="mb-3 text-xs text-text-muted">Fill = recovered share of ₹ at risk for that root cause.</p>
        <div className="rounded-xl border border-border bg-surface-1 px-5 py-2">
          {rootCauseRows.map(([rootCause, b]) => (
            <ProgressRow key={rootCause} label={rootCause} atRisk={b.at_risk} recovered={b.recovered} rate={b.recovery_rate} />
          ))}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-medium text-text-primary">Cases ({visibleCases.length})</h2>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setStatusFilter(null)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                statusFilter === null
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border text-text-secondary hover:border-border-strong"
              }`}
            >
              All
            </button>
            {Object.entries(summary.status_counts).map(([status, count]) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status === statusFilter ? null : status)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  statusFilter === status
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border text-text-secondary hover:border-border-strong"
                }`}
              >
                {status} ({count})
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto rounded-xl border border-border bg-surface-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="px-5 py-3 font-medium">Type</th>
                <th className="px-5 py-3 font-medium">Root cause</th>
                <th className="px-5 py-3 font-medium">Amount</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {visibleCases.map((c) => (
                <tr key={c.id} className="border-b border-border last:border-0 transition-colors hover:bg-surface-2">
                  <td className="px-5 py-3 text-text-secondary">{c.type}</td>
                  <td className="px-5 py-3">
                    <span className="rounded-md bg-surface-2 px-2 py-0.5 text-xs text-text-secondary">
                      {c.root_cause ?? "undiagnosed"}
                    </span>
                  </td>
                  <td className="px-5 py-3 tabular-nums text-text-primary">{formatRs(c.amount)}</td>
                  <td className="px-5 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link href={`/cases/${c.id}`} className="inline-flex items-center gap-1 text-text-muted hover:text-text-primary">
                      Drill in
                      <ArrowRightIcon className="h-3 w-3" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

const LAST_BATCH_KEY = "revenue-recovery.last-batch";

function subscribeToStoredBatch(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getStoredBatch(): string | null {
  try {
    return localStorage.getItem(LAST_BATCH_KEY);
  } catch {
    return null;
  }
}

function getStoredBatchServerSnapshot(): string | null {
  return null;
}

function DashboardContent() {
  const searchParams = useSearchParams();
  const batchFromUrl = searchParams.get("batch");
  const storedBatch = useSyncExternalStore(subscribeToStoredBatch, getStoredBatch, getStoredBatchServerSnapshot);

  // Persist the explicit selection as an external-store write (no state
  // cascade); reads go through useSyncExternalStore above.
  useEffect(() => {
    if (!batchFromUrl) return;
    try {
      localStorage.setItem(LAST_BATCH_KEY, batchFromUrl);
    } catch {
      // best-effort persistence only
    }
  }, [batchFromUrl]);

  const batchId = batchFromUrl ?? storedBatch;

  if (!batchId) {
    return (
      <div className="mx-auto flex max-w-xl flex-col items-center gap-4 px-6 py-24 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">No batch selected</h1>
        <p className="text-sm text-text-secondary">Run a batch first, or pick a past one from history.</p>
        <div className="mt-2 flex gap-3">
          <Link
            href="/run"
            className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-strong"
          >
            Run a batch
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </Link>
          <Link
            href="/history"
            className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-text-primary transition-colors hover:border-border-strong hover:bg-surface-1"
          >
            Browse history
          </Link>
        </div>
      </div>
    );
  }

  return <BatchDashboard key={batchId} batchId={batchId} />;
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-6xl px-6 py-24 text-sm text-text-muted">Loading…</div>}>
      <DashboardContent />
    </Suspense>
  );
}
