"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runBatch, type RunBatchResponse } from "@/lib/api";

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
    <div className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Run a batch</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Generates a synthetic batch of cases and runs the full detection → policy → execution
          pipeline against it.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border border-neutral-800 p-6">
        <label className="flex flex-col gap-1 text-sm">
          Number of cases
          <input
            type="number"
            min={1}
            max={500}
            value={nCases}
            onChange={(e) => setNCases(Number(e.target.value))}
            className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Random seed (optional, for reproducibility)
          <input
            type="text"
            placeholder="leave blank for random"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400 disabled:opacity-50"
        >
          {loading ? "Running…" : "Run batch"}
        </button>
      </form>

      {error && (
        <div className="rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-3 rounded-lg border border-emerald-800 bg-emerald-950/30 p-6">
          <p className="text-sm text-neutral-300">
            Batch <code className="text-emerald-400">{result.batch_id}</code> complete —{" "}
            {result.n_cases} cases, ₹{result.summary.total_recovered.toLocaleString("en-IN")} recovered
            of ₹{result.summary.total_at_risk.toLocaleString("en-IN")} at risk (
            {(result.summary.recovery_rate * 100).toFixed(1)}%).
          </p>
          <button
            onClick={() => router.push(`/dashboard?batch=${result.batch_id}`)}
            className="w-fit rounded-md border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500"
          >
            View full dashboard →
          </button>
        </div>
      )}
    </div>
  );
}
