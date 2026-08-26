"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Scroll-triggered fade-up reveal (see .reveal-init/.reveal-visible in
 * app/globals.css). Plain IntersectionObserver, no animation library -
 * matches this app's zero-dependency convention. `delayMs` staggers a
 * sequence of siblings (e.g. pipeline steps) without needing a parent
 * orchestrator. prefers-reduced-motion is handled entirely in CSS.
 */
export function Reveal({
  children,
  delayMs = 0,
  className = "",
  style,
}: {
  children: React.ReactNode;
  delayMs?: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={visible ? { ...style, animationDelay: `${delayMs}ms` } : style}
      className={`${visible ? "reveal-visible" : "reveal-init"} ${className}`}
    >
      {children}
    </div>
  );
}
