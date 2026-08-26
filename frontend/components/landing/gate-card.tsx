"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The guardrail-proof section's central interaction: a "proposal" face
 * sits in front, hinged at the left edge; once scrolled into view it
 * swings open like a door, uncovering the static "override" face that
 * was behind it the whole time (see .gate-scene/.gate-front in
 * globals.css).
 *
 * Progressive enhancement, not a requirement to access content: the base
 * markup renders both faces stacked in normal document flow (a plain
 * before/after card) - that's what no-JS and prefers-reduced-motion
 * users get, unconditionally. Only once JS confirms motion isn't reduced
 * do the two faces get stacked into the same grid cell and the swing
 * wired up.
 */
export function GateCard({
  kicker,
  icon: Icon,
  proposedAction,
  overrideRule,
  outcome,
}: {
  kicker: string;
  icon: React.ComponentType<{ className?: string }>;
  proposedAction: string;
  overrideRule: string;
  outcome: string;
}) {
  const sceneRef = useRef<HTMLDivElement>(null);
  const [enhanced, setEnhanced] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const node = sceneRef.current;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!node || reducedMotion) return;

    // rAF (not a bare setState in the effect body) switches to the
    // grid-stacked "closed gate" layout on the next frame after mount -
    // hydration-safe (matches the SSR fallback on first paint) without
    // tripping the no-setState-in-effect-body lint rule.
    const enhanceFrame = requestAnimationFrame(() => setEnhanced(true));
    let openFrame: number | undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          // Double rAF: guarantees the closed state actually paints once
          // before flipping open, so the CSS transition has a starting
          // frame to animate from instead of the two states collapsing
          // into a single paint.
          openFrame = requestAnimationFrame(() => {
            openFrame = requestAnimationFrame(() => setOpen(true));
          });
          observer.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(enhanceFrame);
      if (openFrame) cancelAnimationFrame(openFrame);
    };
  }, []);

  const overrideFace = (
    <div className="rounded-lg border border-copper-border bg-copper-fill p-5">
      <div className="flex items-center gap-2 font-numeric text-[11px] uppercase tracking-wider text-copper-bright">
        <Icon className="h-3.5 w-3.5" />
        {kicker}
      </div>
      <p className="font-numeric mt-3 text-sm text-landing-text">{overrideRule}</p>
      <p className="mt-2 text-xs leading-relaxed text-text-muted">{outcome}</p>
    </div>
  );

  const proposalFace = (
    <div className="rounded-lg border border-verdigris-border bg-verdigris-fill p-5">
      <div className="font-numeric text-[11px] uppercase tracking-wider text-verdigris-bright">LLM proposed</div>
      <p className="mt-3 font-numeric text-lg text-landing-text">{proposedAction}</p>
      <p className="mt-2 text-xs leading-relaxed text-text-muted">
        Awaiting the guardrail check that runs before any action executes.
      </p>
    </div>
  );

  if (!enhanced) {
    return (
      <div ref={sceneRef} className="flex flex-col gap-3">
        {proposalFace}
        {overrideFace}
      </div>
    );
  }

  return (
    <div ref={sceneRef} className="gate-scene grid">
      <div className="[grid-area:1/1]">{overrideFace}</div>
      <div className={`gate-front [grid-area:1/1] ${open ? "gate-open" : ""}`}>{proposalFace}</div>
    </div>
  );
}
