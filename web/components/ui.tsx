import { Alert } from "./icons";

export function Note({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "caution" | "danger" | "brand";
  children: React.ReactNode;
}) {
  const colour = {
    muted: "var(--ink-2)",
    caution: "var(--caution)",
    danger: "var(--danger)",
    brand: "var(--brand)",
  }[tone];
  return (
    <p className="text-subhead leading-relaxed" style={{ color: colour }}>
      {children}
    </p>
  );
}

/**
 * The warning surface. Amber in both themes, never pine.
 *
 * This is the only component whose job is to stop someone eating the wrong
 * thing, so it always carries an icon and a heading alongside the colour. In
 * dark mode the sage and the amber sit at almost the same luminance, which
 * means hue alone would separate them for nobody.
 */
export function Caution({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="panel-caution flex gap-3 p-4" style={{ color: "var(--caution)" }}>
      <Alert size={19} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        {title ? <p className="mb-1 text-subhead font-semibold">{title}</p> : null}
        <div className="text-subhead leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-m p-4 text-subhead leading-relaxed"
      style={{
        background: "var(--danger-wash)",
        border: "1px solid var(--danger-line)",
        color: "var(--danger)",
      }}
    >
      <Alert size={19} className="mt-0.5 shrink-0" />
      <span className="min-w-0">{children}</span>
    </div>
  );
}

/**
 * Waiting state. A line of text and a thin rule, which says the same thing as
 * a shimmering placeholder without pretending content has arrived.
 */
export function Waiting({ label }: { label: string }) {
  return (
    <div role="status" className="py-10">
      <p className="text-subhead" style={{ color: "var(--ink-2)" }}>
        {label}
      </p>
      <div className="mt-3 h-px w-full overflow-hidden" style={{ background: "var(--hairline)" }}>
        <div className="h-px w-1/3 animate-pulse" style={{ background: "var(--brand)" }} />
      </div>
    </div>
  );
}

export function Progress({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div>
      <div
        className="h-1 w-full overflow-hidden rounded-s"
        style={{ background: "var(--surface-2)" }}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
      >
        <div
          className="h-full transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%`, background: "var(--brand)" }}
        />
      </div>
    </div>
  );
}

/** Terminal states: expired, missing, already under way. */
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
    <section className="surface p-6">
      <h2 className="font-serif text-title-2">{title}</h2>
      <div className="mt-3">
        <Note>{children}</Note>
      </div>
      {action ? <div className="mt-6">{action}</div> : null}
    </section>
  );
}
