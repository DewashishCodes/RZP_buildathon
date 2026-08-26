"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listBatches, type BatchListItem } from "@/lib/api";

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function shortId(id: string) {
  return id.slice(0, 8);
}

function relativeTime(iso: string | null) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/**
 * Batch history for this merchant: every past run with its outcome, newest
 * first. Clicking one loads it into the dashboard (?batch=). On the
 * dashboard it hides the row already on screen; on /history it shows all.
 */
export function RecentBatches({ merchantId, currentBatchId }: { merchantId: string; currentBatchId?: string }) {
  const [batches, setBatches] = useState<BatchListItem[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    listBatches(merchantId)
      .then((data) => {
        if (!cancelled) setBatches(data);
      })
      .catch(() => {
        if (!cancelled) setBatches([]);
      });
    return () => {
      cancelled = true;
    };
  }, [merchantId]);

  // Only batches other than the one on screen (when embedded in the
  // dashboard - the current one is already fully rendered above).
  const others = (batches ?? []).filter((b) => b.batch_id !== currentBatchId);
  if (batches === null) return <div className="h-20 animate-pulse rounded-xl border border-border bg-surface-1" />;
  if (others.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-1 px-6 py-12 text-center text-sm text-text-muted">
        No batch runs yet for this merchant. Run one from the &quot;Run batch&quot; page.
      </div>
    );
  }

  return (
    <section>
      <h2 className="mb-1 text-lg font-medium text-text-primary">Recent batch runs</h2>
      <p className="mb-3 text-xs text-text-muted">
        Past runs for this merchant - click to load one into the dashboard.
      </p>
      <div className="flex flex-col divide-y divide-border rounded-xl border border-border bg-surface-1 px-5">
        {others.map((b) => (
          <Link
            key={b.batch_id}
            href={`/dashboard?batch=${b.batch_id}`}
            className="group flex items-center gap-4 py-2.5 text-sm transition-colors hover:bg-surface-2"
          >
            <span className="font-mono text-xs text-text-secondary">{shortId(b.batch_id)}</span>
            {b.phase === "failed" ? (
              <span className="rounded-md bg-status-critical-bg px-2 py-0.5 text-xs text-status-critical">failed</span>
            ) : (
              <span className="text-xs text-text-muted">{relativeTime(b.created_at)}</span>
            )}
            <span className="text-xs text-text-muted">{b.total_cases} cases</span>
            <span className="ml-auto tabular-nums text-text-primary">{formatRs(b.total_recovered)}</span>
            <span
              className={`w-14 text-right tabular-nums ${
                b.recovery_rate > 0 ? "text-status-good" : "text-text-muted"
              }`}
            >
              {(b.recovery_rate * 100).toFixed(1)}%
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
