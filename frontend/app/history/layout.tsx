import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Batch history — Janus",
};

export default function HistoryLayout({ children }: LayoutProps<"/history">) {
  return children;
}
