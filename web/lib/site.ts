/**
 * The site's own absolute origin.
 *
 * Open Graph URLs must be absolute. Without a `metadataBase` Next resolves
 * them against localhost, so every link pasted into a group chat unfurls
 * pointing at a machine nobody else can reach, breaking the only
 * distribution channel this product has.
 *
 * Order matters: an explicit value wins, then Vercel's stable production
 * domain, then the per-deployment URL, then local dev.
 */
export function siteUrl(): URL {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL;
  if (explicit) return new URL(explicit);

  const production = process.env.VERCEL_PROJECT_PRODUCTION_URL;
  if (production) return new URL(`https://${production}`);

  const deployment = process.env.VERCEL_URL;
  if (deployment) return new URL(`https://${deployment}`);

  return new URL("http://localhost:3000");
}
