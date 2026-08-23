import Link from "next/link";
import { ArrowRightIcon, PhoneIcon, ShieldIcon, SwapIcon } from "@/components/icons";

const STEPS = [
  {
    icon: SwapIcon,
    title: "Detect & diagnose",
    body: "Rules-first classification for unambiguous decline codes, Gemini fallback for ambiguous ones — every case gets a root cause, not a guess.",
  },
  {
    icon: ShieldIcon,
    title: "Propose & guard",
    body: "An LLM proposes a bounded action; deterministic code enforces stopping rules and compliance before anything executes.",
  },
  {
    icon: PhoneIcon,
    title: "Execute & recover",
    body: "Mock channel connectors — nudge, SMS, email, voice, human — carry out the approved action against a hidden recoverability model.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-12 px-6 py-24">
      <div className="flex flex-col gap-4">
        <span className="w-fit rounded-full border border-border bg-surface-1 px-3 py-1 text-xs font-medium text-text-secondary">
          Razorpay Buildathon · Track 03
        </span>
        <h1 className="text-4xl font-semibold tracking-tight text-text-primary">
          AI Revenue Recovery Agent
        </h1>
        <p className="max-w-xl text-base leading-relaxed text-text-secondary">
          Detects revenue at risk across payment/mandate failures and B2B receivables, diagnoses
          root cause, proposes a bounded recovery action, enforces hard-coded guardrails, and
          reports measured recovery with a full audit trail.
        </p>
      </div>

      <div className="flex gap-3">
        <Link
          href="/run"
          className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
        >
          Run a batch
          <ArrowRightIcon className="h-3.5 w-3.5" />
        </Link>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-text-primary transition-colors hover:border-border-strong hover:bg-surface-1"
        >
          View dashboard
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {STEPS.map((step) => (
          <div key={step.title} className="rounded-xl border border-border bg-surface-1 p-5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <step.icon className="h-4 w-4" />
            </span>
            <h2 className="mt-3 text-sm font-semibold text-text-primary">{step.title}</h2>
            <p className="mt-1.5 text-xs leading-relaxed text-text-muted">{step.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
