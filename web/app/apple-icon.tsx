import { ImageResponse } from "next/og";

/** Home screen icon for iOS, which will not take the SVG favicon. */
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
          background: "#24503F",
        }}
      >
        <svg width="112" height="112" viewBox="0 0 32 32" fill="none">
          <g fill="#FDFBF6">
            <rect x="10.4" y="7" width="1.5" height="6" rx="0.4" />
            <rect x="14.05" y="7" width="1.5" height="6" rx="0.4" />
            <rect x="17.7" y="7" width="1.5" height="6" rx="0.4" />
            <path d="M10.4 12.4h8.8v1.1a4.4 4.4 0 0 1-8.8 0v-1.1Z" />
            <rect x="13.9" y="16.4" width="2.2" height="8.6" rx="0.5" />
          </g>
        </svg>
      </div>
    ),
    size,
  );
}
