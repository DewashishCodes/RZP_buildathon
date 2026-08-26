import { Reveal } from "@/components/reveal";

const INCIDENTS = [
  {
    id: "01",
    problem: "A burst of Gemini API calls tripped the free-tier rate limit mid-batch, silently deflating recovery numbers via a fail-safe fallback.",
    fix: "A client-side rate limiter, exponential backoff, and response caching.",
  },
  {
    id: "02",
    problem: "A simulated-clock/wall-clock mismatch silently discarded LLM-chosen retry dates.",
    fix: "Threaded the simulated clock through the whole call chain.",
  },
  {
    id: "03",
    problem: "Timestamp collisions in the audit log broke chronological ordering.",
    fix: "Switched to a database-generated clock instead of application-generated timestamps.",
  },
  {
    id: "04",
    problem: "The test suite had quietly accumulated years of leftover data with zero isolation.",
    fix: "Transaction-per-test isolation - which immediately surfaced a real hidden bug: one test silently depended on another's leftover data.",
  },
];

/**
 * A log, not a marketing bullet list - plain problem/fix pairs in the
 * monospace face, on a darker inset surface to read as a terminal/incident
 * tracker rather than a feature section.
 */
export function Postmortem() {
  return (
    <section className="flex flex-col gap-6">
      <div className="text-center">
        <h2 className="font-display text-2xl text-landing-text">What broke, and how we got out</h2>
      </div>
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-3">
        {INCIDENTS.map((incident, i) => (
          <Reveal key={incident.id} delayMs={i * 80}>
            <div className="rounded-lg border border-border bg-surface-2 p-5">
              <div className="font-numeric text-[11px] uppercase tracking-wider text-copper-bright">
                incident {incident.id}
              </div>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{incident.problem}</p>
              <div className="mt-3 flex items-baseline gap-2 border-t border-border pt-3">
                <span className="font-numeric text-[11px] uppercase tracking-wider text-verdigris-bright">fix</span>
                <p className="text-sm leading-relaxed text-text-primary">{incident.fix}</p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
