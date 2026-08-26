"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  getBatchGuardrails,
  getBatchProgress,
  getBatchSummary,
  listCases,
  runBatch,
  type BatchProgress,
  type DemoStop,
  type RunBatchResponse,
} from "@/lib/api";
import { useMerchant } from "@/components/merchant-context";
import { ArrowRightIcon } from "@/components/icons";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/**
 * Derives the PRD §15 demo-script drill-downs from a finished batch so the
 * live walkthrough is click-to-story: recovered insufficient_funds case,
 * card_expired link case, guardrail escalations, and the DND substitution
 * moment straight from the guardrails feed.
 */
async function buildDemoStops(batchId: string): Promise<DemoStop[]> {
  const [cases, interventions] = await Promise.all([
    listCases({ batchId }),
    getBatchGuardrails(batchId).catch(() => []),
  ]);
  const stops: DemoStop[] = [];

  const recovered = cases.find((c) => c.root_cause === "insufficient_funds" && c.status === "recovered");
  if (recovered)
    stops.push({
      label: "1 · Root-cause reasoning that paid",
      description: "insufficient_funds → payday-aligned retry → recovered. Show the timeline.",
      href: `/cases/${recovered.id}`,
    });

  const linkCase = cases.find((c) => c.root_cause === "card_expired");
  if (linkCase)
    stops.push({
      label: "2 · No blind retries",
      description: "card_expired got an update-payment-method link instead of another debit attempt.",
      href: `/cases/${linkCase.id}`,
    });

  const substitutions = interventions.filter((i) => i.kind === "compliance_substitution");
  for (const [i, sub] of substitutions.entries()) {
    stops.push({
      label: `3${i > 0 ? "b" : ""} · Compliance rewrote the LLM`,
      description: `${sub.rule}: ${sub.reason ?? "voice blocked"}. The proposal was not allowed through.`,
      href: `/cases/${sub.case_id}`,
    });
    break; // one is enough for the script
  }

  const escalated = cases.filter((c) => c.status === "escalated_human").slice(0, 2);
  for (const [i, esc] of escalated.entries()) {
    stops.push({
      label: `4${i > 0 ? "b" : ""} · Stopping rule fired`,
      description: `${esc.root_cause ?? "case"} hit a hard cap and went to a human - with an auto-opened ticket.`,
      href: `/cases/${esc.id}`,
    });
  }

  return stops;
}

type RunPhase = "idle" | "starting" | "polling" | "done" | "failed";

function RunBatchPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const demoMode = searchParams.get("demo") === "1";
  const { merchantId, merchants, loading: merchantLoading } = useMerchant();
  const [nCases, setNCases] = useState(demoMode ? 10 : 50);
  const [seed, setSeed] = useState<string>(demoMode ? "42" : "");
  const [instant, setInstant] = useState(true);
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<BatchProgress | null>(null);
  const [result, setResult] = useState<RunBatchResponse | null>(null);
  const [demoStops, setDemoStops] = useState<DemoStop[] | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!merchantId || phase === "starting" || phase === "polling") return;
    setPhase("starting");
    setError(null);
    setResult(null);
    setProgress(null);

    let batchId: string;
    try {
      const parsedSeed = seed.trim() === "" ? null : Number(seed);
      // Background mode: the pipeline can take a while (real Gemini calls,
      // paced by the rate limiter), so we get a batch_id back immediately
      // and watch it work instead of holding a single request open.
      const started = await runBatch({ merchantId, nCases, seed: parsedSeed, instant, background: true });
      batchId = started.batch_id;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start batch");
      setPhase("failed");
      return;
    }

    setPhase("polling");
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const p = await getBatchProgress(batchId);
        setProgress(p);
        if (p.phase === "complete") {
          stopPolling();
          const summary = await getBatchSummary(batchId);
          setResult({
            batch_id: batchId,
            n_customers: p.total_cases,
            n_cases: p.total_cases,
            summary,
          });
          if (demoMode) {
            buildDemoStops(batchId)
              .then(setDemoStops)
              .catch(() => setDemoStops([]));
          }
          setPhase("done");
        } else if (p.phase === "failed") {
          stopPolling();
          setError(p.error ?? "Batch failed");
          setPhase("failed");
        }
      } catch {
        // Transient poll errors (server restart mid-run etc.) - keep trying
        // until the user navigates away; the next tick may succeed.
      }
    }, 1500);
  }

  const busy = phase === "starting" || phase === "polling";
  const activeMerchant = merchants.find((m) => m.id === merchantId);

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Run a batch</h1>
        <p className="mt-1.5 text-sm text-text-secondary">
          Generates a synthetic batch of cases and runs the full detection → policy → execution
          pipeline against it, live, for <span className="text-text-primary">{activeMerchant?.name ?? "…"}</span>.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5 rounded-xl border border-border bg-surface-1 p-6">
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-text-primary">Number of cases</span>
          <input
            type="number"
            min={1}
            max={500}
            value={nCases}
            onChange={(e) => setNCases(Number(e.target.value))}
            className="rounded-lg border border-border-strong bg-surface-2 px-3 py-2 text-text-primary outline-none focus:border-accent"
          />
          <span className="text-xs text-text-muted">
            Gemini calls are paced client-side (~15/min); larger batches just take longer, watching live below.
          </span>
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-text-primary">Random seed</span>
          <input
            type="text"
            placeholder="leave blank for random"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            className="rounded-lg border border-border-strong bg-surface-2 px-3 py-2 text-text-primary outline-none focus:border-accent"
          />
        </label>

        <div className="flex items-start gap-3 rounded-lg border border-border-strong bg-surface-2 px-3.5 py-3">
          <input
            id="instant"
            type="checkbox"
            checked={!instant}
            onChange={(e) => setInstant(!e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-accent"
          />
          <label htmlFor="instant" className="text-sm">
            <span className="font-medium text-text-primary">Realistic scheduling mode</span>
            <p className="mt-0.5 text-xs text-text-muted">
              Each case runs exactly one round, then queues its next action for real instead of
              resolving instantly — proves the batch isn&apos;t secretly fast-forwarding time. Check
              the dashboard&apos;s Scheduled Actions panel afterward, or process due jobs manually.
            </p>
          </label>
        </div>

        <button
          type="submit"
          disabled={busy || merchantLoading || !merchantId}
          className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong disabled:opacity-50"
        >
          {phase === "starting" ? "Starting…" : phase === "polling" ? "Running…" : "Run batch"}
          {!busy && <ArrowRightIcon className="h-3.5 w-3.5" />}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-status-critical/30 bg-status-critical-bg px-4 py-3 text-sm text-status-critical">
          {error}
        </div>
      )}

      {progress && busy && (
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-1 p-6">
          <div className="flex items-baseline justify-between">
            <p className="text-sm font-medium text-text-primary">Agent working…</p>
            <p className="text-xs tabular-nums text-text-muted">
              {progress.resolved_cases}/{progress.total_cases} cases resolved
            </p>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-accent transition-all duration-500"
              style={{ width: `${Math.round((progress.resolved_cases / Math.max(progress.total_cases, 1)) * 100)}%` }}
            />
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-xs text-text-muted">Recovered so far</span>
              <div className="mt-0.5 text-lg font-semibold tabular-nums text-status-good">
                {formatRs(progress.recovered_amount)}
              </div>
            </div>
            <div>
              <span className="text-xs text-text-muted">Cases recovered</span>
              <div className="mt-0.5 text-lg font-semibold tabular-nums text-text-primary">
                {progress.recovered_cases}
              </div>
            </div>
          </div>
          <p className="text-xs text-text-muted">{progress.phase === "queued" ? "Queued…" : "Detection → policy → execution, one case at a time."}</p>
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-4 rounded-xl border border-status-good/30 bg-status-good-bg p-6">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Batch complete</p>
            <p className="mt-1 font-mono text-xs text-text-secondary">{result.batch_id}</p>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-text-muted">Cases</div>
              <div className="mt-0.5 text-lg font-semibold text-text-primary">{result.n_cases}</div>
            </div>
            <div>
              <div className="text-xs text-text-muted">Recovered</div>
              <div className="mt-0.5 text-lg font-semibold text-status-good">
                {formatRs(result.summary.total_recovered)}
              </div>
            </div>
            <div>
              <div className="text-xs text-text-muted">Recovery rate</div>
              <div className="mt-0.5 text-lg font-semibold text-status-good">
                {(result.summary.recovery_rate * 100).toFixed(1)}%
              </div>
            </div>
          </div>
          <button
            onClick={() => router.push(`/dashboard?batch=${result.batch_id}`)}
            className="inline-flex w-fit items-center gap-2 rounded-full border border-border-strong px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-2"
          >
            View full dashboard
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {demoStops && demoStops.length > 0 && (
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-1 p-6">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Demo script · PRD §15</p>
            <p className="mt-1 text-sm text-text-secondary">
              This batch contains every story the walkthrough needs. Walk them in order:
            </p>
          </div>
          {demoStops.map((stop) => (
            <button
              key={stop.href}
              onClick={() => router.push(stop.href)}
              className="group flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3 text-left transition-colors hover:border-border-strong hover:bg-surface-2"
            >
              <span>
                <span className="block text-sm font-medium text-text-primary">{stop.label}</span>
                <span className="mt-0.5 block text-xs text-text-muted">{stop.description}</span>
              </span>
              <ArrowRightIcon className="h-3.5 w-3.5 shrink-0 text-text-muted group-hover:text-text-primary" />
            </button>
          ))}
          <button
            onClick={() => router.push(`/dashboard?batch=${result?.batch_id ?? ""}`)}
            className="inline-flex w-fit items-center gap-1.5 text-xs text-text-muted hover:text-text-primary"
          >
            …or open the full dashboard for this batch
            <ArrowRightIcon className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}

export default function RunBatchPageWithSuspense() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-xl px-6 py-24 text-sm text-text-muted">Loading…</div>}>
      <RunBatchPage />
    </Suspense>
  );
}
