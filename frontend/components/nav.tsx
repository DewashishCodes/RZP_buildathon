"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMerchant } from "./merchant-context";

const LINKS = [
  { href: "/run", label: "Run batch" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/history", label: "History" },
  { href: "/tickets", label: "Support tickets" },
];

function MerchantSwitcher() {
  const { merchants, merchantId, setMerchantId, loading } = useMerchant();

  if (loading || merchants.length === 0) {
    return <div className="h-8 w-40 animate-pulse rounded-md bg-surface-2" />;
  }

  return (
    <select
      value={merchantId ?? ""}
      onChange={(e) => setMerchantId(e.target.value)}
      className="rounded-md border border-border-strong bg-surface-1 px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
      aria-label="Active merchant"
    >
      {merchants.map((m) => (
        <option key={m.id} value={m.id}>
          {m.name}
        </option>
      ))}
    </select>
  );
}

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-plane/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent text-xs font-bold text-white">
              J
            </span>
            <span className="text-sm font-semibold tracking-tight text-text-primary">Janus</span>
          </Link>
          <div className="flex items-center gap-1">
            {LINKS.map((link) => {
              const active = pathname?.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                    active ? "bg-surface-2 text-text-primary" : "text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
        <MerchantSwitcher />
      </nav>
    </header>
  );
}
