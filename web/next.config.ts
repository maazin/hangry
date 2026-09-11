import type { NextConfig } from "next";

/**
 * Response headers applied to every route.
 *
 * The referrer policy is the one that matters here. The results screen links
 * out to OpenStreetMap, and without this a click would hand that site the
 * full round URL in the `Referer` header, which is enough for a stranger to
 * open the group. The link itself already carries `rel="noreferrer"`; this
 * covers every other way a URL can leak.
 */
const securityHeaders = [
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), payment=(), interest-cohort=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
