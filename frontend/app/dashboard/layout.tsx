import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — AI Revenue Recovery Agent",
};

export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  return children;
}
