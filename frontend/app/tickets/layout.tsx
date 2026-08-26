import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Support tickets — AI Revenue Recovery Agent",
};

export default function TicketsLayout({ children }: LayoutProps<"/tickets">) {
  return children;
}
