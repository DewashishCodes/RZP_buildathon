"use client";

import { BoltIcon, MailIcon, PhoneIcon, UserIcon } from "@/components/icons";
import { Reveal } from "@/components/reveal";

/**
 * Ascending, not just sequential: each step sits visually higher than the
 * last (increasing translateY offset + a rising connector), so escalation
 * reads as a literal climb rather than four equal boxes in a row - this
 * is deliberately distinct from the Pipeline's connected-corridor
 * treatment, since it's about contact intensity, not the decision flow.
 */
const STEPS = [
  { icon: BoltIcon, label: "Silent retry / nudge" },
  { icon: MailIcon, label: "SMS / email" },
  { icon: PhoneIcon, label: "Voice call (Hinglish)" },
  { icon: UserIcon, label: "Human escalation" },
];

export function ChannelLadder() {
  return (
    <section className="flex flex-col gap-8">
      <div className="text-center">
        <h2 className="font-display text-2xl text-landing-text">One case, an escalating ladder</h2>
        <p className="mt-1 text-sm text-text-secondary">Contact intensity rises only as far as the case demands.</p>
      </div>
      <div className="flex items-end justify-center gap-3 sm:gap-5">
        {STEPS.map((step, i) => (
          <Reveal key={step.label} delayMs={i * 100} style={{ marginBottom: `${i * 14}px` }}>
            <div className="flex w-24 flex-col items-center gap-2 rounded-lg border border-border bg-surface-1 p-4 text-center transition-colors duration-150 hover:border-copper-border sm:w-32">
              <span
                className="flex h-8 w-8 items-center justify-center rounded-lg"
                style={{ background: "var(--copper-fill)", color: `color-mix(in srgb, var(--copper) ${40 + i * 15}%, var(--copper-bright))` }}
              >
                <step.icon className="h-4 w-4" />
              </span>
              <p className="text-[11px] leading-snug text-text-secondary">{step.label}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
