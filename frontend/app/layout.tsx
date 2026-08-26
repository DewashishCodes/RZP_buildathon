import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { fraunces, jetbrainsMono } from "@/lib/fonts";
import { Nav } from "@/components/nav";
import { MerchantProvider } from "@/components/merchant-context";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Janus — AI Revenue Recovery Agent",
  description: "Razorpay Buildathon — Track 03: AI Revenue Recovery",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <MerchantProvider>
          <Nav />
          <main className="flex-1">{children}</main>
        </MerchantProvider>
      </body>
    </html>
  );
}
