"use client";

import { useEffect, useState } from "react";
import { getBatchCurve, type CurvePoint } from "@/lib/api";
import { TrendUpIcon } from "./icons";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/**
 * Cumulative ₹ recovered across the batch's processing timeline - a single
 * rising line proving money actually moved while the agent worked. Hand-
 * drawn inline SVG (no chart library) to keep the bundle at zero deps.
 */
export function RecoveryChart({ batchId }: { batchId: string }) {
  const [points, setPoints] = useState<CurvePoint[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getBatchCurve(batchId)
      .then((data) => {
        if (!cancelled) setPoints(data);
      })
      .catch(() => {
        if (!cancelled) setPoints([]);
      });
    return () => {
      cancelled = true;
    };
  }, [batchId]);

  if (points === null) return <div className="h-40 animate-pulse rounded-xl border border-border bg-surface-1" />;
  if (points.length < 2) return null;

  const W = 600;
  const H = 140;
  const PAD = 6;
  const max = points[points.length - 1].cumulative_recovered;
  if (max <= 0) return null;

  const xs = points.map((_, i) => PAD + (i / (points.length - 1)) * (W - 2 * PAD));
  const ys = points.map((p) => H - PAD - (p.cumulative_recovered / max) * (H - 2 * PAD));
  const line = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const area = `${line} L${xs[xs.length - 1].toFixed(1)},${H - PAD} L${PAD},${H - PAD} Z`;

  return (
    <section>
      <div className="mb-1 flex items-center gap-2">
        <TrendUpIcon className="h-4 w-4 text-status-good" />
        <h2 className="text-lg font-medium text-text-primary">Recovery over time</h2>
        <span className="ml-auto text-sm font-semibold tabular-nums text-status-good">{formatRs(max)}</span>
      </div>
      <p className="mb-3 text-xs text-text-muted">Cumulative ₹ recovered as the agent worked through the batch.</p>
      <div className="rounded-xl border border-border bg-surface-1 p-4">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Cumulative recovered amount rising over the batch">
          {/* gridlines */}
          {[0.25, 0.5, 0.75].map((f) => (
            <line
              key={f}
              x1={PAD}
              x2={W - PAD}
              y1={H - PAD - f * (H - 2 * PAD)}
              y2={H - PAD - f * (H - 2 * PAD)}
              stroke="currentColor"
              className="text-gridline"
              strokeWidth="1"
              strokeDasharray="3 5"
            />
          ))}
          <path d={area} fill="currentColor" className="text-status-good opacity-10" />
          <path
            d={line}
            fill="none"
            stroke="currentColor"
            className="text-status-good"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {points.map((p, i) => (
            <circle key={i} cx={xs[i]} cy={ys[i]} r="3" fill="currentColor" className="text-status-good">
              <title>{`${formatRs(p.cumulative_recovered)} · ${p.timestamp ? new Date(p.timestamp).toLocaleTimeString() : ""}`}</title>
            </circle>
          ))}
        </svg>
      </div>
    </section>
  );
}
