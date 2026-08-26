import Link from "next/link";
import { listBatches, type BatchListItem } from "@/lib/api";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  BoltIcon,
  ChatIcon,
  MailIcon,
  PhoneIcon,
  ShieldIcon,
  SwapIcon,
  UserIcon,
  XCircleIcon,
} from "@/components/icons";
import { StatTile } from "@/components/stat-tile";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function shortId(id: string) {
  return id.slice(0, 8);
}

async function getLatestBatch(): Promise<BatchListItem | null> {
  try {
    const batches = await listBatches();
    return batches[0] ?? null;
  } catch {
    // Backend unreachable (e.g. a fresh clone with nothing running yet) -
    // degrade to the same empty-state CTA as "no batches yet" rather than
    // hard-failing the landing page.
    return null;
  }
}

/**
 * Live proof, not a mocked-up number: the most recent batch across every
 * tenant, however it was actually produced. The disclaimer underneath is
 * load-bearing - these are real pipeline outputs against a synthetic
 * environment, not live production transactions.
 */
async function ProofStrip() {
  const batch = await getLatestBatch();

  if (!batch) {
    return (
      <div className="flex flex-col gap-4">
        <div className="rounded-xl border border-border bg-surface-1 px-6 py-10 text-center">
          <p className="text-sm text-text-secondary">
            No batch has run yet on this instance - the numbers here populate the moment one does.
          </p>
          <Link
            href="/run?demo=1"
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
          >
            Run the demo batch
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </Link>
        </div>
        <p className="text-center text-xs leading-relaxed text-text-muted">
          Every number on this page comes from a real run of the actual pipeline against a
          simulated payments/receivables environment with a hidden recoverability model - not
          live production transactions.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="₹ at risk" value={formatRs(batch.total_at_risk)} />
        <StatTile label="₹ recovered" value={formatRs(batch.total_recovered)} accent="good" />
        <StatTile label="Recovery rate" value={`${(batch.recovery_rate * 100).toFixed(1)}%`} accent="accent" />
      </div>
      <Link
        href={`/dashboard?batch=${batch.batch_id}`}
        className="inline-flex w-fit items-center gap-1.5 text-xs text-text-muted transition-colors hover:text-text-secondary"
      >
        From batch <span className="font-mono">{shortId(batch.batch_id)}</span> ({batch.total_cases} cases) — view
        full dashboard
        <ArrowRightIcon className="h-3 w-3" />
      </Link>
      <p className="text-xs leading-relaxed text-text-muted">
        Real pipeline output, not a mockup - but against a simulated payments/receivables
        environment with a hidden recoverability model, not live production transactions.
      </p>
    </div>
  );
}

const PIPELINE_STEPS = [
  { icon: SwapIcon, title: "Detect", body: "Every open case gets flagged as revenue at risk, across three leak types." },
  { icon: ChatIcon, title: "Diagnose", body: "Rules-first for unambiguous codes, Gemini fallback for ambiguous ones." },
  { icon: BoltIcon, title: "Propose", body: "An LLM proposes one bounded action from a fixed action space." },
  { icon: ShieldIcon, title: "Guardrail", body: "Deterministic code can override or substitute the proposal outright." },
  { icon: PhoneIcon, title: "Execute", body: "The approved action runs; the outcome is recorded either way." },
];

function PipelineStep({ step, index, isLast }: { step: (typeof PIPELINE_STEPS)[number]; index: number; isLast: boolean }) {
  return (
    <div className="relative flex flex-1 flex-col gap-3 rounded-xl border border-border bg-surface-1 p-5">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-accent">
          <step.icon className="h-4 w-4" />
        </span>
        <span className="text-xs font-medium text-text-muted">{index + 1}</span>
      </div>
      <h3 className="text-sm font-semibold text-text-primary">{step.title}</h3>
      <p className="text-xs leading-relaxed text-text-muted">{step.body}</p>
      {!isLast && (
        <ArrowRightIcon className="absolute top-1/2 -right-[22px] hidden h-3.5 w-3.5 -translate-y-1/2 text-border-strong md:block" />
      )}
    </div>
  );
}

function GuardrailExample({
  icon: Icon,
  kicker,
  proposed,
  overrideLabel,
  outcome,
}: {
  icon: React.ComponentType<{ className?: string }>;
  kicker: string;
  proposed: string;
  overrideLabel: string;
  outcome: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-1 p-5">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-text-muted">
        <Icon className="h-3.5 w-3.5" />
        {kicker}
      </div>
      <p className="mt-3 text-sm text-text-secondary">
        LLM proposed <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-text-primary">{proposed}</span>
      </p>
      <p className="mt-2 text-sm text-text-primary">{overrideLabel}</p>
      <p className="mt-2 text-xs leading-relaxed text-text-muted">{outcome}</p>
    </div>
  );
}

const CHANNEL_STEPS = [
  { icon: BoltIcon, label: "Silent retry / nudge" },
  { icon: MailIcon, label: "SMS / email" },
  { icon: PhoneIcon, label: "Voice call (Hinglish)" },
  { icon: UserIcon, label: "Human escalation" },
];

const CREDIBILITY_FACTS = [
  "173 backend tests, transaction-isolated",
  "One-command Docker Compose",
  "Idempotent batch runs",
  "Structured JSON audit log",
  "Rate-limited + retried LLM calls",
];

export default async function Home() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-20 px-6 py-20">
      {/* Hero */}
      <div className="mx-auto flex max-w-3xl flex-col gap-4 text-center sm:text-left">
        <span className="mx-auto w-fit rounded-full border border-border bg-surface-1 px-3 py-1 text-xs font-medium text-text-secondary sm:mx-0">
          Razorpay Buildathon · Track 03
        </span>
        <h1 className="text-4xl font-semibold tracking-tight text-text-primary">
          Janus
          <span className="ml-3 align-middle text-base font-medium text-text-muted">AI Revenue Recovery Agent</span>
        </h1>
        <p className="max-w-xl text-base leading-relaxed text-text-secondary sm:max-w-none">
          Named for the god of thresholds: detects revenue at risk across payment/mandate
          failures and B2B receivables, diagnoses root cause, proposes a bounded recovery action,
          enforces hard-coded guardrails at every doorway it opens, and reports measured recovery
          with a full audit trail.
        </p>
        <div className="mt-2 flex justify-center gap-3 sm:justify-start">
          <Link
            href="/run?demo=1"
            className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
          >
            Run demo batch
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-text-primary transition-colors hover:border-border-strong hover:bg-surface-1"
          >
            View dashboard
          </Link>
        </div>
      </div>

      {/* Live proof strip */}
      <section className="flex flex-col gap-4">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">Measured, not simulated away</h2>
        <ProofStrip />
      </section>

      {/* Pipeline */}
      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-lg font-medium text-text-primary">How it works</h2>
          <p className="mt-1 text-sm text-text-secondary">One case, five steps, every one of them logged.</p>
        </div>
        <div className="flex flex-col gap-4 md:flex-row">
          {PIPELINE_STEPS.map((step, i) => (
            <PipelineStep key={step.title} step={step} index={i} isLast={i === PIPELINE_STEPS.length - 1} />
          ))}
        </div>
      </section>

      {/* Guardrails highlight */}
      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-lg font-medium text-text-primary">The LLM proposes. It doesn&apos;t decide.</h2>
          <p className="mt-1 max-w-2xl text-sm text-text-secondary">
            Stopping rules and compliance checks are plain deterministic Python with their own
            unit tests - not prompt instructions the model can talk its way around.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <GuardrailExample
            icon={AlertTriangleIcon}
            kicker="Stopping rule"
            proposed="retry_now"
            overrideLabel="Guardrail: fraud_or_dispute_auto_escalate"
            outcome="Escalated straight to a human - no further automated contact attempted, no exceptions."
          />
          <GuardrailExample
            icon={ShieldIcon}
            kicker="Compliance substitution"
            proposed="voice_call"
            overrideLabel="DND rule substituted: send_reminder"
            outcome="A do-not-disturb customer never receives the call the model wanted to make."
          />
        </div>
      </section>

      {/* Channel ladder */}
      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-lg font-medium text-text-primary">One case, an escalating ladder</h2>
          <p className="mt-1 text-sm text-text-secondary">Contact intensity rises only as far as the case demands.</p>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {CHANNEL_STEPS.map((step) => (
            <div key={step.label} className="flex flex-col items-center gap-2 rounded-xl border border-border bg-surface-1 p-5 text-center">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-accent">
                <step.icon className="h-4 w-4" />
              </span>
              <p className="text-xs leading-relaxed text-text-secondary">{step.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Breadth */}
      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface-1 p-5">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <XCircleIcon className="h-4 w-4" />
            </span>
            <h3 className="text-sm font-semibold text-text-primary">Payment &amp; mandate failures</h3>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-text-muted">
            Failed card/UPI debits and revoked subscription mandates, root-caused down to
            insufficient funds, expired cards, issuer declines, bank timeouts, and more.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-surface-1 p-5">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <MailIcon className="h-4 w-4" />
            </span>
            <h3 className="text-sm font-semibold text-text-primary">B2B receivables</h3>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-text-muted">
            Overdue invoices bucketed by how late they are, with disputes routed straight to
            human escalation instead of an automated nudge.
          </p>
        </div>
      </section>

      {/* Engineering credibility */}
      <section className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 border-y border-border py-5 text-center">
        {CREDIBILITY_FACTS.map((fact) => (
          <span key={fact} className="text-xs text-text-muted">
            {fact}
          </span>
        ))}
      </section>

      {/* Final CTA */}
      <section className="flex flex-col items-center gap-4 text-center">
        <h2 className="text-xl font-medium text-text-primary">See it work end to end</h2>
        <div className="flex gap-3">
          <Link
            href="/run?demo=1"
            className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
          >
            Run demo batch
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </Link>
          <Link
            href="/history"
            className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-text-primary transition-colors hover:border-border-strong hover:bg-surface-1"
          >
            Browse history
          </Link>
        </div>
        <p className="mt-4 text-xs text-text-muted">Janus — built for Razorpay Buildathon, Track 03.</p>
      </section>
    </div>
  );
}
