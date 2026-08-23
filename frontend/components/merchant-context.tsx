"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { listMerchants, type Merchant } from "@/lib/api";

const STORAGE_KEY = "revenue-recovery.merchant-id";

interface MerchantContextValue {
  merchants: Merchant[];
  merchantId: string | null;
  setMerchantId: (id: string) => void;
  loading: boolean;
}

const MerchantContext = createContext<MerchantContextValue | null>(null);

export function MerchantProvider({ children }: { children: React.ReactNode }) {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [merchantId, setMerchantIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMerchants()
      .then((list) => {
        setMerchants(list);
        let stored: string | null = null;
        try {
          stored = localStorage.getItem(STORAGE_KEY);
        } catch {
          // localStorage unavailable (private mode, etc.) - fall through to default
        }
        const initial = list.find((m) => m.id === stored)?.id ?? list[0]?.id ?? null;
        setMerchantIdState(initial);
      })
      .finally(() => setLoading(false));
  }, []);

  function setMerchantId(id: string) {
    setMerchantIdState(id);
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // best-effort persistence only
    }
  }

  return (
    <MerchantContext.Provider value={{ merchants, merchantId, setMerchantId, loading }}>
      {children}
    </MerchantContext.Provider>
  );
}

export function useMerchant(): MerchantContextValue {
  const ctx = useContext(MerchantContext);
  if (!ctx) throw new Error("useMerchant must be used within a MerchantProvider");
  return ctx;
}
