"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMerchant } from "@/components/merchant-context";
import { listTickets, type Ticket } from "@/lib/api";
import { PriorityBadge, TicketStatusBadge } from "@/components/status-badge";
import { ArrowRightIcon } from "@/components/icons";

interface LoadState {
  tickets: Ticket[];
  error: string | null;
}

function useMerchantTickets(merchantId: string): LoadState {
  const [state, setState] = useState<LoadState>({ tickets: [], error: null });

  useEffect(() => {
    let cancelled = false;
    listTickets({ merchantId })
      .then((tickets) => {
        if (!cancelled) setState({ tickets, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ tickets: [], error: err instanceof Error ? err.message : "Failed to load tickets" });
      });
    return () => {
      cancelled = true;
    };
  }, [merchantId]);

  return state;
}

function MerchantTicketsList({ merchantId }: { merchantId: string }) {
  const { tickets, error } = useMerchantTickets(merchantId);

  if (error) {
    return (
      <div className="rounded-lg border border-status-critical/30 bg-status-critical-bg px-4 py-3 text-sm text-status-critical">
        {error}
      </div>
    );
  }

  if (tickets.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-1 px-6 py-12 text-center text-sm text-text-muted">
        No tickets yet. Escalated cases will show up here automatically.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
            <th className="px-5 py-3 font-medium">Subject</th>
            <th className="px-5 py-3 font-medium">Priority</th>
            <th className="px-5 py-3 font-medium">Status</th>
            <th className="px-5 py-3 font-medium">Assignee</th>
            <th className="px-5 py-3 font-medium">Opened</th>
            <th className="px-5 py-3 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((t) => (
            <tr key={t.id} className="border-b border-border last:border-0 transition-colors hover:bg-surface-2">
              <td className="px-5 py-3">
                <div className="text-text-primary">{t.subject}</div>
                <div className="mt-0.5 text-xs text-text-muted">{t.reason}</div>
              </td>
              <td className="px-5 py-3">
                <PriorityBadge priority={t.priority} />
              </td>
              <td className="px-5 py-3">
                <TicketStatusBadge status={t.status} />
              </td>
              <td className="px-5 py-3 text-text-secondary">{t.assignee}</td>
              <td className="px-5 py-3 text-text-muted">{new Date(t.created_at).toLocaleString()}</td>
              <td className="px-5 py-3 text-right">
                <Link
                  href={`/cases/${t.case_id}`}
                  className="inline-flex items-center gap-1 text-text-muted hover:text-text-primary"
                >
                  View case
                  <ArrowRightIcon className="h-3 w-3" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TicketsPage() {
  const { merchantId, merchants, loading: merchantLoading } = useMerchant();
  const activeMerchant = merchants.find((m) => m.id === merchantId);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Support tickets</h1>
        <p className="mt-1.5 text-sm text-text-secondary">
          Auto-opened whenever a case escalates to a human for{" "}
          <span className="text-text-primary">{activeMerchant?.name ?? "…"}</span> — this is where
          escalate_human actually lands, not a dead end.
        </p>
      </div>

      {merchantLoading || !merchantId ? (
        <div className="py-12 text-sm text-text-muted">Loading…</div>
      ) : (
        <MerchantTicketsList key={merchantId} merchantId={merchantId} />
      )}
    </div>
  );
}
