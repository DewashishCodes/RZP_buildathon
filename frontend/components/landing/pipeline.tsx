"use client";

import { ChatIcon, PhoneIcon, ShieldIcon, SwapIcon, BoltIcon } from "@/components/icons";
import { Reveal } from "@/components/reveal";

/**
 * Detect/Diagnose/Propose are the retrospective face (verdigris) - working
 * out what happened and what should happen next. Guardrail/Execute are
 * the prospective face (copper) - what's actually allowed to happen. The
 * connector between Propose and Guardrail is where the color grammar
 * turns over, because that's the actual pivot point in the system: the
 * moment a suggestion either survives contact with deterministic code or
 * doesn't.
 */
const STEPS = [
  { icon: SwapIcon, title: "Detect", body: "Every open case is flagged as revenue at risk, across three leak types.", face: "verdigris" as const },
  { icon: ChatIcon, title: "Diagnose", body: "Rules-first for unambiguous decline codes, Gemini fallback for ambiguous ones.", face: "verdigris" as const },
  { icon: BoltIcon, title: "Propose", body: "An LLM proposes exactly one action from a fixed, bounded action space.", face: "verdigris" as const },
  { icon: ShieldIcon, title: "Guardrail", body: "Deterministic, unit-tested code can override or substitute the proposal.", face: "copper" as const },
  { icon: PhoneIcon, title: "Execute", body: "The approved action runs; the outcome is recorded either way.", face: "copper" as const },
];

const FACE_CLASSES = {
  verdigris: {
    border: "hover:border-verdigris-border",
    chip: "bg-verdigris-fill text-verdigris-bright",
    label: "text-verdigris-bright",
  },
  copper: {
    border: "hover:border-copper-border",
    chip: "bg-copper-fill text-copper-bright",
    label: "text-copper-bright",
  },
};

export function Pipeline() {
  return (
    <section className="flex flex-col gap-8">
      <div className="text-center">
        <h2 className="font-display text-2xl text-landing-text">How it works</h2>
        <p className="mt-1 text-sm text-text-secondary">One case, five steps, every one of them logged.</p>
      </div>
      <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
        {STEPS.map((step, i) => {
          const classes = FACE_CLASSES[step.face];
          const isLast = i === STEPS.length - 1;
          const isPivot = i === 2; // connector leaving "Propose" crosses into the copper face
          return (
            <Reveal key={step.title} delayMs={i * 90} className="relative flex flex-1">
              <div
                className={`group flex flex-1 flex-col gap-3 rounded-t-2xl rounded-b-lg border border-border bg-surface-1 p-5 transition-colors duration-150 ${classes.border}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${classes.chip}`}>
                    <step.icon className="h-4 w-4" />
                  </span>
                  <span className="font-numeric text-[11px] text-text-muted">0{i + 1}</span>
                </div>
                <h3 className="text-sm font-semibold text-text-primary">{step.title}</h3>
                <p className="text-xs leading-relaxed text-text-muted">{step.body}</p>
                <span className={`font-numeric mt-auto text-[10px] uppercase tracking-wider ${classes.label}`}>
                  {step.face === "verdigris" ? "retrospective" : "prospective"}
                </span>
              </div>
              {!isLast && (
                <div
                  className="signal-line absolute top-1/2 -right-3 hidden h-px w-3 -translate-y-1/2 md:block"
                  style={{ background: isPivot ? "var(--copper-border)" : "var(--border-strong)" }}
                >
                  <span
                    className="signal-dot"
                    style={{
                      animationDelay: `${i * 0.35}s`,
                      background: isPivot ? "var(--copper)" : "var(--verdigris)",
                      boxShadow: `0 0 6px 1px ${isPivot ? "var(--copper)" : "var(--verdigris)"}`,
                    }}
                  />
                </div>
              )}
            </Reveal>
          );
        })}
      </div>
    </section>
  );
}
