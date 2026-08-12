import { ImageResponse } from "next/og";

/**
 * The link-preview card.
 *
 * This is a growth surface, not decoration: the only way Hangry spreads is
 * one person pasting a link into a group chat, and a bare URL gets scrolled
 * past. Rendered at request time by `next/og` so there's no binary asset to
 * keep in sync with the brand.
 */
export const runtime = "edge";
export const alt = "Hangry — settle where the group eats";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "76px 80px",
          background: "linear-gradient(135deg, #12B76A 0%, #067647 55%, #05502F 100%)",
          color: "#fff",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {/* The real mark, not an emoji — Satori has no colour emoji font, so
              🍴 renders as a grey glyph and quietly breaks the brand. */}
          <svg width="70" height="70" viewBox="0 0 32 32" fill="none">
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
              stroke="#067647"
              strokeWidth="2.1"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <div style={{ fontSize: 44, fontWeight: 700, letterSpacing: "-0.03em" }}>Hangry</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 82, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1.04 }}>
            Where are we
          </div>
          <div style={{ fontSize: 82, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1.04 }}>
            eating?
          </div>
          <div style={{ marginTop: 26, fontSize: 31, opacity: 0.86, letterSpacing: "-0.01em" }}>
            Tap in what you can&apos;t eat. Rank a few places. Done in 30 seconds.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {["No signup", "No download", "One link"].map((label) => (
            <div
              key={label}
              style={{
                display: "flex",
                padding: "12px 24px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.16)",
                border: "1px solid rgba(255,255,255,0.28)",
                fontSize: 25,
                fontWeight: 600,
              }}
            >
              {label}
            </div>
          ))}
        </div>
      </div>
    ),
    size,
  );
}
