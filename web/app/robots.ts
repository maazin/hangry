import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/site";

/**
 * Keep group and round links out of search results.
 *
 * These URLs are unlisted rather than protected: anyone holding one can open
 * it and read the roster, which carries real names and dietary restrictions,
 * including allergies. That trade is fine for a link someone pastes into
 * their own group chat, and it stops being fine the moment a crawler puts
 * the same link in an index. The landing page stays open.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/g/", "/s/"] }],
    sitemap: new URL("/sitemap.xml", siteUrl()).toString(),
  };
}
