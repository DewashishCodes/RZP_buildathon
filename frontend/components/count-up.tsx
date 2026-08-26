"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Animates a number from 0 to `value` on scroll-into-view - the "proof strip
 * numbers are actually moving" moment. Plain requestAnimationFrame, no
 * animation library. Snaps straight to the final value under
 * prefers-reduced-motion or once the observed element leaves without ever
 * intersecting (SSR/no-JS fallback: the server-rendered text node already
 * shows `format(value)`, so nothing is ever blank).
 */
export function CountUp({
  value,
  prefix = "",
  suffix = "",
  durationMs = 900,
  decimals = 0,
}: {
  value: number;
  prefix?: string;
  suffix?: string;
  durationMs?: number;
  decimals?: number;
}) {
  // A function prop (e.g. an Intl formatter closure) can't cross the
  // server/client boundary from an async Server Component - formatting
  // happens here instead, driven by plain serializable props.
  const format = (n: number) =>
    `${prefix}${n.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`;

  const ref = useRef<HTMLSpanElement>(null);
  // Seeded with the final value (not 0) so server-rendered HTML and the
  // first client render always match - the count-from-0 animation only
  // starts once the observer confirms the element is in view and motion
  // isn't reduced, both decided inside the effect below, never at the
  // initial render.
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const node = ref.current;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!node || reducedMotion) return;

    let frame: number;
    let start: number | null = null;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        setDisplay(0);

        const step = (timestamp: number) => {
          if (start === null) start = timestamp;
          const progress = Math.min((timestamp - start) / durationMs, 1);
          const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
          const scale = 10 ** decimals;
          setDisplay(Math.round(value * eased * scale) / scale);
          if (progress < 1) frame = requestAnimationFrame(step);
        };
        frame = requestAnimationFrame(step);
      },
      { threshold: 0.3 },
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [value, durationMs, decimals]);

  return <span ref={ref}>{format(display)}</span>;
}
