import { Fraunces, JetBrains_Mono } from "next/font/google";

/**
 * Landing-page-only type pairing (see components/landing/*): a display
 * serif for headline gravitas, a monospace for anything numeric or
 * code-adjacent - myth vs. engineering, echoing the two-faces motif.
 * Scoped to the landing page's own wrapper via these CSS vars rather than
 * the root layout, so the rest of the app (dashboard, nav, etc.) keeps
 * Geist untouched.
 */
export const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

export const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});
