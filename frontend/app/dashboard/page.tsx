"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getBatchSummary, listCases, type BatchSummary, type CaseSummary } from "@/lib/api";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

const STATUS_COLORS: Record<string, string> = {
  recovered: "text-emerald-400",
  escalated_human: "text-amber-400",
  written_off: "text-red-400",
  recovering: "text-blue-400",
  open: "text-neutral-400",
};

function DashboardContent() {
  const searchParams = useSearchParams();
  const batchId = searchParams.get("batch");

  const [summary, setSummary] = useState<BatchSummary | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!batchId) return;
    setLoading(true);
    setError(null);
    Promise.all([getBatchSummary(batchId), listCases({ batchId })])
      .then(([s, c]) => {
        setSummary(s);
        setCases(c);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load batch"))
      .finally(() => setLoading(false));
  }, [batchId]);

  if (!batchId) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-neutral-400">No batch selected.</p>
        <Link href="/run" className="w-fit rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400">
          Run a batch
        </Link>
      </div>
    );
  }

  if (loading) {
    return <div className="mx-auto max-w-5xl px-6 py-16 text-neutral-400">Loading…</div>;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <div className="rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-300">{error}</div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Batch summary</h1>
        <p className="mt-1 text-sm text-neutral-500">
          <code>{summary.batch_id}</code>
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="₹ at risk" value={formatRs(summary.total_at_risk)} />
        <StatCard label="₹ recovered" value={formatRs(summary.total_recovered)} accent="text-emerald-400" />
        <StatCard label="Recovery rate" value={`${(summary.recovery_rate * 100).toFixed(1)}%`} accent="text-emerald-400" />
        <StatCard label="Cases" value={String(summary.total_cases)} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard
          label="Stopping-rule triggers"
          value={String(summary.stopping_rule_triggers)}
          hint="proof guardrails fired, not just existed"
        />
        <StatCard
          label="Compliance substitutions"
          value={String(summary.compliance_substitutions)}
          hint="proof compliance logic changed behavior"
        />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-medium">Recovery by root cause</h2>
        <div className="overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-900 text-left text-neutral-400">
              <tr>
                <th className="px-4 py-2 font-medium">Root cause</th>
                <th className="px-4 py-2 font-medium">At risk</th>
                <th className="px-4 py-2 font-medium">Recovered</th>
                <th className="px-4 py-2 font-medium">Rate</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.by_root_cause).map(([rootCause, b]) => (
                <tr key={rootCause} className="border-t border-neutral-800">
                  <td className="px-4 py-2">{rootCause}</td>
                  <td className="px-4 py-2">{formatRs(b.at_risk)}</td>
                  <td className="px-4 py-2">{formatRs(b.recovered)}</td>
                  <td className="px-4 py-2">{(b.recovery_rate * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium">Cases ({cases.length})</h2>
        <div className="overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-900 text-left text-neutral-400">
              <tr>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Root cause</th>
                <th className="px-4 py-2 font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id} className="border-t border-neutral-800">
                  <td className="px-4 py-2">{c.type}</td>
                  <td className="px-4 py-2">{c.root_cause ?? "—"}</td>
                  <td className="px-4 py-2">{formatRs(c.amount)}</td>
                  <td className={`px-4 py-2 ${STATUS_COLORS[c.status] ?? ""}`}>{c.status}</td>
                  <td className="px-4 py-2">
                    <Link href={`/cases/${c.id}`} className="text-neutral-400 hover:text-white">
                      Drill in →
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

function StatCard({ label, value, accent, hint }: { label: string; value: string; accent?: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 p-4">
      <div className="text-xs text-neutral-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${accent ?? ""}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-neutral-600">{hint}</div>}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-5xl px-6 py-16 text-neutral-400">Loading…</div>}>
      <DashboardContent />
    </Suspense>
  );
}
