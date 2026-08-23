import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-20">
      <h1 className="text-3xl font-semibold tracking-tight">AI Revenue Recovery Agent</h1>
      <p className="text-neutral-400">
        Detects revenue at risk across payment/mandate failures and B2B receivables, diagnoses
        root cause, proposes a bounded recovery action, enforces hard-coded guardrails, and
        reports measured recovery with a full audit trail.
      </p>
      <div className="flex gap-4">
        <Link
          href="/run"
          className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400"
        >
          Run a batch
        </Link>
        <Link
          href="/dashboard"
          className="rounded-md border border-neutral-700 px-4 py-2 text-sm font-medium hover:border-neutral-500"
        >
          View dashboard
        </Link>
      </div>
    </div>
  );
}
