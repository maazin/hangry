import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

/**
 * One family, tight tracking, optical sizing on. Inter is the closest
 * widely-available face to the neutral grotesque Apple uses, and next/font
 * self-hosts it so there's no third-party request on the joiner's first
 * paint — which is the only paint most of them will wait for.
 */
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
  axes: ["opsz"],
});

export const metadata: Metadata = {
  title: "Hangry — settle it",
  description:
    "Six people, one link, thirty seconds each. Hangry picks somewhere everyone can actually eat — and shows you what the popular answer would have cost.",
  applicationName: "Hangry",
  openGraph: {
    title: "Where are we eating?",
    description: "Tap in what you can't eat, rank a few places, and Hangry settles it. No signup.",
    type: "website",
    siteName: "Hangry",
  },
  twitter: {
    card: "summary_large_image",
    title: "Where are we eating?",
    description: "Tap in what you can't eat, rank a few places, and Hangry settles it. No signup.",
  },
};

export const viewport: Viewport = {
  // Matches the page background in each scheme so the iOS status bar and the
  // browser chrome don't sit in a different colour to the app.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f9f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0f0c" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-dvh font-sans antialiased">
        <div className="mx-auto w-full max-w-[480px] px-5 pb-20 pt-8">{children}</div>
      </body>
    </html>
  );
}
