import type { Metadata } from "next";

import { GroupView } from "@/components/GroupView";

/**
 * The group link is the one that lives in the chat's pinned messages, so its
 * preview card has to read as an invitation to join people rather than an
 * advert for software.
 */
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const title = "Join the group";
  const description =
    "Say once what you can't eat, and every meal this group picks will already know. No signup, no download.";

  // `images` has to be repeated here. Declaring `openGraph` in a child route
  // replaces the parent's object wholesale, which silently drops the image
  // Next injects from app/opengraph-image.tsx. Without this the invite
  // link unfurls as a plain text card.
  const images = ["/opengraph-image"];

  return {
    title,
    description,
    openGraph: { title, description, type: "website", siteName: "Hangry", url: `/g/${slug}`, images },
    twitter: { card: "summary_large_image", title, description, images },
  };
}

export default async function GroupPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <GroupView slug={slug.toUpperCase()} />;
}
