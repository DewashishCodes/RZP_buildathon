"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getBatchGuardrails, type GuardrailIntervention } from "@/lib/api";
import { AlertTriangleIcon, ArrowRightIcon, SwapIcon } from "./icons";

/**
 * The stories behind the dashboard's two proof counters: every stopping-rule
 * fire and every compliance substitution in the batch, newest first. Turns
 * "guardrails fired 10 times" into a clickable list - the "proof guardrails
 * aren't decorative" moment judges can drill into.
 */
export function GuardrailFeed({ batchId }: { batchId: string }) {
  const [items, setItems] = useState<GuardrailIntervention[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getBatchGuardrails(batchId)
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      });
    return () => {
      cancelled = true;
    };
  }, [batchId]);

  if (error) return null;
  if (items === null) {
    return <div className="h-24 animate-pulse rounded-xl border border-border bg-surface-1" />;
  }
  if (items.length === 0) return null;

  return (
    <section>
      <h2 className="mb-1 text-lg font-medium text-text-primary">Guardrails in action ({items.length})</h2>
      <p className="mb-3 text-xs text-text-muted">
        Every stopping-rule fire and compliance substitution in this batch - proof they change behavior, not just exist.
      </p>
      <div className="flex flex-col divide-y divide-border rounded-xl border border-border bg-surface-1 px-5">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-3 py-2.5 text-sm">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                item.kind === "stopping_rule"
                  ? "bg-status-warning-bg text-status-warning"
                  : "bg-accent/10 text-accent"
              }`}
            >
              {item.kind === "stopping_rule" ? <AlertTriangleIcon className="h-3.5 w-3.5" /> : <SwapIcon className="h-3.5 w-3.5" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate font-mono text-xs text-text-primary">{item.rule ?? item.event_type}</div>
              <div className="truncate text-xs text-text-muted">{item.reason}</div>
            </div>
            <Link
              href={`/cases/${item.case_id}`}
              aria-label="Open case"
              className="inline-flex shrink-0 items-center gap-1 text-xs text-text-muted hover:text-text-primary"
            >
              Case
              <ArrowRightIcon className="h-3 w-3" />
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}
