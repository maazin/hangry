export function Wordmark({ tagline }: { tagline?: string }) {
  return (
    <header className="mb-6">
      <h1 className="text-3xl font-black tracking-tight" style={{ color: "var(--accent)" }}>
        Hangry
      </h1>
      {tagline ? (
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {tagline}
        </p>
      ) : null}
    </header>
  );
}

export function Note({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "warn" | "danger" | "ok";
  children: React.ReactNode;
}) {
  const colour = { muted: "var(--muted)", warn: "var(--warn)", danger: "var(--danger)", ok: "var(--ok)" }[tone];
  return (
    <p className="text-sm leading-relaxed" style={{ color: colour }}>
      {children}
    </p>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="rounded-xl border px-4 py-3 text-sm"
      style={{ borderColor: "var(--danger)", color: "var(--danger)", background: "rgb(242 112 79 / 0.08)" }}
    >
      {children}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-8" role="status">
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-transparent"
        style={{ borderTopColor: "var(--accent)", borderRightColor: "var(--accent)" }}
      />
      <span className="text-sm" style={{ color: "var(--muted)" }}>
        {label}
      </span>
    </div>
  );
}

/** Skeleton rows, so a slow solve reads as working rather than broken. */
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-2xl" style={{ background: "var(--surface-2)" }} />
      ))}
    </div>
  );
}
