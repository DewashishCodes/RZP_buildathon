import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Support tickets — Janus",
};

export default function TicketsLayout({ children }: LayoutProps<"/tickets">) {
  return children;
}
