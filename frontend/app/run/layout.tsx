import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Run a batch — Janus",
};

export default function RunLayout({ children }: LayoutProps<"/run">) {
  return children;
}
