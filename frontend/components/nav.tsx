"use client";

import Image from "next/image";
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
    <header
      className="sticky top-0 z-20 border-b bg-plane/80 backdrop-blur"
      style={{ borderImage: "linear-gradient(to right, var(--verdigris-border), var(--border), var(--copper-border)) 1" }}
    >
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="relative flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-2 ring-1 ring-border-strong">
              <Image src="/janus-logo.png" alt="Janus" width={28} height={28} className="h-[85%] w-[85%] object-contain" />
            </span>
            <span className="font-display text-base font-medium tracking-tight text-text-primary">Janus</span>
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
