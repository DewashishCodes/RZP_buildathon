"use client";

import { useMerchant } from "@/components/merchant-context";
import { RecentBatches } from "@/components/recent-batches";

export default function HistoryPage() {
  const { merchantId, merchants, loading: merchantLoading } = useMerchant();
  const activeMerchant = merchants.find((m) => m.id === merchantId);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Batch history</h1>
        <p className="mt-1.5 text-sm text-text-secondary">
          Every recovery run for <span className="text-text-primary">{activeMerchant?.name ?? "…"}</span>, newest
          first. Click a run to open its full dashboard.
        </p>
      </div>

      {merchantLoading || !merchantId ? (
        <div className="py-12 text-sm text-text-muted">Loading…</div>
      ) : (
        <RecentBatches key={merchantId} merchantId={merchantId} />
      )}
    </div>
  );
}
