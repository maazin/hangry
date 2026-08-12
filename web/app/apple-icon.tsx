import { ImageResponse } from "next/og";

/** Home-screen icon for iOS, which won't take the SVG favicon. */
export const runtime = "edge";
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #12B76A 0%, #067647 100%)",
        }}
      >
        <svg width="122" height="122" viewBox="0 0 32 32" fill="none">
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
      </div>
    ),
    size,
  );
}
