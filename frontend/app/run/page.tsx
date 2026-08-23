"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runBatch, type RunBatchResponse } from "@/lib/api";
import { ArrowRightIcon } from "@/components/icons";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export default function RunBatchPage() {
  const router = useRouter();
  const [nCases, setNCases] = useState(50);
  const [seed, setSeed] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunBatchResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const parsedSeed = seed.trim() === "" ? null : Number(seed);
      const response = await runBatch(nCases, parsedSeed);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run batch");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Run a batch</h1>
        <p className="mt-1.5 text-sm text-text-secondary">
          Generates a synthetic batch of cases and runs the full detection → policy → execution
          pipeline against it, live.
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
          <span className="text-xs text-text-muted">Keep this modest (~10-20) to stay under Gemini&apos;s free-tier burst rate limit.</span>
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
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong disabled:opacity-50"
        >
          {loading ? "Running…" : "Run batch"}
          {!loading && <ArrowRightIcon className="h-3.5 w-3.5" />}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-status-critical/30 bg-status-critical-bg px-4 py-3 text-sm text-status-critical">
          {error}
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
    </div>
  );
}
