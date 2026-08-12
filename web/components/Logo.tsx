/**
 * The mark: a fork with a tick.
 *
 * A fork alone says "food app". The tick is what makes it this food app —
 * the product's whole claim is that the argument is over. Drawn as solid
 * paths rather than strokes so it stays crisp at favicon sizes.
 */
export function Mark({ size = 32, className }: { size?: number; className?: string }) {
  const id = "mark-brand";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      role="img"
      aria-label="Hangry"
    >
      <rect width="32" height="32" rx="7.5" fill={`url(#${id})`} />
      <g fill="#fff">
        <rect x="10.55" y="6.6" width="1.35" height="5.3" rx="0.67" />
        <rect x="13.45" y="6.6" width="1.35" height="5.3" rx="0.67" />
        <rect x="16.35" y="6.6" width="1.35" height="5.3" rx="0.67" />
        <path d="M10.55 11.5h7.15v1.2a3.575 3.575 0 0 1-7.15 0v-1.2Z" />
        <rect x="13.03" y="15.4" width="2.2" height="9.9" rx="1.1" />
      </g>
      <circle cx="23.1" cy="22.2" r="5.9" fill="#fff" />
      <path
        d="m20.5 22.3 1.85 1.95 3.75-4.2"
        stroke={`url(#${id})`}
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#12B76A" />
          <stop offset="1" stopColor="#067647" />
        </linearGradient>
      </defs>
    </svg>
  );
}

/** Mark plus wordmark. `tagline` is the one line of context under it. */
export function Logo({ tagline, size = 30 }: { tagline?: string; size?: number }) {
  return (
    <header className="mb-7">
      <div className="flex items-center gap-2.5">
        <Mark size={size} />
        <span className="text-[22px] font-bold" style={{ letterSpacing: "-0.035em" }}>
          Hangry
        </span>
      </div>
      {tagline ? (
        <p className="mt-3 text-[15px] leading-snug" style={{ color: "var(--text-2)" }}>
          {tagline}
        </p>
      ) : null}
    </header>
  );
}
