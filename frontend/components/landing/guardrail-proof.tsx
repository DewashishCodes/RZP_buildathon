"use client";

import { AlertTriangleIcon, ShieldIcon } from "@/components/icons";
import { GateCard } from "./gate-card";
import { Reveal } from "@/components/reveal";

/**
 * The single strongest credibility claim on the page: an LLM's proposal
 * doesn't get to execute on its own say-so. Each example is a door - the
 * proposal swings open to reveal what a plain, unit-tested function
 * decided instead. See components/landing/gate-card.tsx.
 */
export function GuardrailProof() {
  return (
    <section className="flex flex-col gap-8">
      <div className="mx-auto max-w-xl text-center">
        <h2 className="font-display text-2xl text-landing-text">The LLM proposes. It doesn&apos;t decide.</h2>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
          Stopping rules and compliance checks are plain deterministic Python functions with their
          own unit tests - not prompt instructions the model can talk its way around.
        </p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2">
        <Reveal delayMs={0}>
          <GateCard
            kicker="Stopping rule"
            icon={AlertTriangleIcon}
            proposedAction="retry_now"
            overrideRule="fraud_or_dispute_auto_escalate"
            outcome="Escalated straight to a human - no further automated contact attempted, no exceptions."
          />
        </Reveal>
        <Reveal delayMs={150}>
          <GateCard
            kicker="Compliance substitution"
            icon={ShieldIcon}
            proposedAction="voice_call"
            overrideRule="DND rule substituted: send_reminder"
            outcome="A do-not-disturb customer never receives the call the model wanted to make."
          />
        </Reveal>
      </div>
    </section>
  );
}
