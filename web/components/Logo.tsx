/*
 * The mark is a single fork, cut square. No badge, no gradient, no second
 * idea competing with the first. At 16px the silhouette still reads, which
 * is the only test a favicon has to pass.
 */
export function Mark({ size = 26, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className={className} role="img" aria-label="Hangry">
      <rect width="32" height="32" rx="2" fill="var(--brand)" />
      <g fill="var(--on-brand)">
        <rect x="10.4" y="7" width="1.5" height="6" rx="0.4" />
        <rect x="14.05" y="7" width="1.5" height="6" rx="0.4" />
        <rect x="17.7" y="7" width="1.5" height="6" rx="0.4" />
        <path d="M10.4 12.4h8.8v1.1a4.4 4.4 0 0 1-8.8 0v-1.1Z" />
        <rect x="13.9" y="16.4" width="2.2" height="8.6" rx="0.5" />
      </g>
    </svg>
  );
}

/**
 * Masthead. `context` names the group or the moment, and sits in the serif so
 * the page has one line of voice before the interface takes over.
 */
export function Masthead({ context }: { context?: string }) {
  return (
    <header className="mb-8">
      <div className="flex items-center gap-2.5">
        <Mark />
        <span className="text-title-3 font-semibold tracking-[-0.02em]">Hangry</span>
      </div>
      {context ? (
        <p className="mt-4 font-serif text-title-3 leading-snug" style={{ color: "var(--ink-2)" }}>
          {context}
        </p>
      ) : null}
    </header>
  );
}
