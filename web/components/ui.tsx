import { Alert } from "./icons";

export function Note({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "warn" | "danger" | "brand";
  children: React.ReactNode;
}) {
  const colour = {
    muted: "var(--text-2)",
    warn: "var(--warn)",
    danger: "var(--danger)",
    brand: "var(--brand)",
  }[tone];
  return (
    <p className="text-[14px] leading-relaxed" style={{ color: colour }}>
      {children}
    </p>
  );
}

/**
 * The warning surface. Amber in both themes, never green — this is the only
 * component on screen whose job is to stop someone from eating the wrong
 * thing, so it must never read as part of the brand.
 */
export function Callout({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="panel-warn flex gap-3 p-4" style={{ color: "var(--warn)" }}>
      <Alert size={19} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        {title ? <p className="mb-1 text-[14px] font-semibold">{title}</p> : null}
        <div className="text-[14px] leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="flex gap-3 p-4 text-[14px] leading-relaxed"
      style={{
        background: "var(--danger-tint)",
        border: "1px solid var(--danger-border)",
        borderRadius: "var(--r)",
        color: "var(--danger)",
      }}
    >
      <Alert size={19} className="mt-0.5 shrink-0" />
      <span className="min-w-0">{children}</span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10" role="status">
      <span
        className="h-[18px] w-[18px] animate-spin rounded-full border-2"
        style={{ borderColor: "var(--border-strong)", borderTopColor: "var(--brand)" }}
      />
      {label ? (
        <span className="text-[14px]" style={{ color: "var(--text-2)" }}>
          {label}
        </span>
      ) : null}
    </div>
  );
}

/** Skeleton rows, so a slow solve reads as working rather than broken. */
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="h-9 w-2/5 animate-pulse rounded" style={{ background: "var(--surface-2)" }} />
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse"
          style={{ height: 68, borderRadius: "var(--r)", background: "var(--surface-2)" }}
        />
      ))}
    </div>
  );
}

export function Progress({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full"
      style={{ background: "var(--surface-2)" }}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
    >
      <div
        className="h-full rounded-full transition-[width] duration-500 ease-out"
        style={{ width: `${pct}%`, background: "var(--brand)" }}
      />
    </div>
  );
}

/** Terminal states — expired, not found, already started. */
export function Stopped({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="card p-6">
      <h2 className="text-[21px] font-bold">{title}</h2>
      <div className="mt-2">
        <Note>{children}</Note>
      </div>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
