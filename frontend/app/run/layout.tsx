import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Run a batch — AI Revenue Recovery Agent",
};

export default function RunLayout({ children }: LayoutProps<"/run">) {
  return children;
}
