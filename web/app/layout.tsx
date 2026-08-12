import type { Metadata, Viewport } from "next";
import "./globals.css";

/**
 * OG tags are a growth feature, not polish. A link that renders as a bare
 * URL in a group chat gets scrolled past; the whole distribution model is
 * one person pasting this into iMessage, WhatsApp, or Discord.
 */
export const metadata: Metadata = {
  title: "Hangry — settle it",
  description:
    "Six people, one link, fifteen seconds each. Hangry picks somewhere everyone can actually eat — and shows you what the popular answer would have cost.",
  openGraph: {
    title: "Where are we eating?",
    description: "Tap in your dietary needs, rank a few places, and Hangry settles it. No signup.",
    type: "website",
    siteName: "Hangry",
  },
  twitter: {
    card: "summary_large_image",
    title: "Where are we eating?",
    description: "Tap in your dietary needs, rank a few places, and Hangry settles it. No signup.",
  },
};

export const viewport: Viewport = {
  themeColor: "#17130f",
  width: "device-width",
  initialScale: 1,
  // Joiners are on phones; let them zoom if they need to.
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh antialiased">
        <div className="mx-auto w-full max-w-lg px-4 pb-16 pt-6">{children}</div>
      </body>
    </html>
  );
}
