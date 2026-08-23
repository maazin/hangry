import type { Metadata, Viewport } from "next";
import { Instrument_Sans, Instrument_Serif } from "next/font/google";

import { siteUrl } from "@/lib/site";
import "./globals.css";

/*
 * Two families, each with one job. Instrument Sans runs the interface, where
 * legibility at 13px matters more than personality. Instrument Serif appears
 * only on the few lines that carry weight: the headline and the name of the
 * restaurant the group is going to. Keeping the serif rare is what stops it
 * reading as decoration.
 *
 * Both are self hosted by next/font, so no request leaves for a third party
 * on the joiner's first paint.
 */
const sans = Instrument_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  variable: "--font-serif",
});

export const metadata: Metadata = {
  // Without this, Open Graph URLs resolve against localhost and a link shared
  // into a group chat points at a machine nobody else can reach.
  metadataBase: siteUrl(),
  title: "Hangry",
  description:
    "Six people, one link. Hangry settles where the group eats, and shows what the popular answer would have cost.",
  applicationName: "Hangry",
  openGraph: {
    title: "Where are we eating?",
    description: "Say what you cannot eat, rank a few places, and Hangry settles it. No signup.",
    type: "website",
    siteName: "Hangry",
  },
  twitter: {
    card: "summary_large_image",
    title: "Where are we eating?",
    description: "Say what you cannot eat, rank a few places, and Hangry settles it. No signup.",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f1ea" },
    { media: "(prefers-color-scheme: dark)", color: "#131311" },
  ],
  width: "device-width",
  initialScale: 1,
  // Left open so people can pinch to enlarge, which the HIG asks for.
  maximumScale: 5,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable}`}>
      <body className="min-h-dvh font-sans antialiased">
        <div className="mx-auto w-full max-w-[30rem] px-5 pb-24 pt-9">{children}</div>
      </body>
    </html>
  );
}
