import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Batch history — AI Revenue Recovery Agent",
};

export default function HistoryLayout({ children }: LayoutProps<"/history">) {
  return children;
}
