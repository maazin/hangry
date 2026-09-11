import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

/** Only the landing page. Everything else is somebody's private dinner. */
export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: siteUrl().toString(), changeFrequency: "monthly", priority: 1 }];
}
