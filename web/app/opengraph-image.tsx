import { ImageResponse } from "next/og";

/*
 * The link preview card. The only way Hangry travels is one person pasting a
 * link into a group chat, so this is a distribution surface rather than
 * decoration. Flat pine, one question, generous margins.
 */
export const runtime = "edge";
export const alt = "Hangry, settle where the group eats";
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
          padding: "84px 88px",
          background: "#24503F",
          color: "#FDFBF6",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <svg width="46" height="46" viewBox="0 0 32 32" fill="none">
            <g fill="#FDFBF6">
              <rect x="10.4" y="7" width="1.5" height="6" rx="0.4" />
              <rect x="14.05" y="7" width="1.5" height="6" rx="0.4" />
              <rect x="17.7" y="7" width="1.5" height="6" rx="0.4" />
              <path d="M10.4 12.4h8.8v1.1a4.4 4.4 0 0 1-8.8 0v-1.1Z" />
              <rect x="13.9" y="16.4" width="2.2" height="8.6" rx="0.5" />
            </g>
          </svg>
          <div style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.02em" }}>Hangry</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 92, fontWeight: 600, letterSpacing: "-0.035em", lineHeight: 1.02 }}>
            Where are we eating?
          </div>
          <div style={{ marginTop: 30, fontSize: 30, opacity: 0.82, letterSpacing: "-0.01em" }}>
            Say what you cannot eat. Rank a few places. Thirty seconds.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
