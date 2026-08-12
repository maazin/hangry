/**
 * A small line-icon set drawn on one grid: 24px box, 1.75 stroke, round caps.
 * Consistency here is most of what separates a considered interface from an
 * assembled one — and it replaces the ▲/▼/⠿ text glyphs, which rendered at a
 * different weight on every platform.
 */
type IconProps = { size?: number; className?: string; style?: React.CSSProperties };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
});

export const Check = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <path d="m4.5 12.5 5 5 10-11" />
  </svg>
);

export const ChevronUp = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <path d="m6 14.5 6-6 6 6" />
  </svg>
);

export const ChevronDown = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <path d="m6 9.5 6 6 6-6" />
  </svg>
);

export const Grip = ({ size = 20, className, style }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" style={style} className={className} aria-hidden>
    {[8, 12, 16].map((y) => (
      <g key={y}>
        <circle cx="9.5" cy={y} r="1.35" />
        <circle cx="14.5" cy={y} r="1.35" />
      </g>
    ))}
  </svg>
);

export const Pin = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
    <circle cx="12" cy="10" r="2.6" />
  </svg>
);

export const Share = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <path d="M12 15.5V3.5m0 0L8 7.5m4-4 4 4" />
    <path d="M5 13.5v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" />
  </svg>
);

export const Alert = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5.5M12 16.4v.2" />
  </svg>
);

export const Users = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <circle cx="9" cy="8.5" r="3.2" />
    <path d="M3.5 19.5a5.5 5.5 0 0 1 11 0M16 5.6a3.2 3.2 0 0 1 0 5.9M17.5 14.4a5.5 5.5 0 0 1 3 5.1" />
  </svg>
);

export const ArrowRight = ({ size = 20, className, style }: IconProps) => (
  <svg {...base(size)} className={className} style={style}>
    <path d="M4.5 12h15m0 0-5.5-5.5M19.5 12 14 17.5" />
  </svg>
);
