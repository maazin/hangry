import type { Metadata } from "next";

import { SessionView } from "@/components/SessionView";

/**
 * The link lands in a group chat, so the preview card is doing the recruiting.
 * Kept per-slug rather than global so the unfurl reads as an invitation to a
 * specific group rather than an advert for a product.
 */
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const title = "Where are we eating?";
  const description = "Tap in what you can't eat, rank a few places, and Hangry settles it. No signup, about 30 seconds.";

  // See the note in app/g/[slug]/page.tsx — a child `openGraph` replaces the
  // parent's, so the generated image has to be named again or the link
  // unfurls without it.
  const images = ["/opengraph-image"];

  return {
    title,
    description,
    openGraph: { title, description, type: "website", siteName: "Hangry", url: `/s/${slug}`, images },
    twitter: { card: "summary_large_image", title, description, images },
  };
}

export default async function SessionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <SessionView slug={slug.toUpperCase()} />;
}
