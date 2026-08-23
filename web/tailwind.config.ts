import type { Config } from "tailwindcss";

export default {
  content: ["./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "ui-serif", "Georgia", "serif"],
      },
      // Mirrors the custom properties in globals.css so utilities and
      // component classes cannot drift into two different palettes.
      colors: {
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        hairline: "var(--hairline)",
        ink: "var(--ink)",
        "ink-2": "var(--ink-2)",
        "ink-3": "var(--ink-3)",
        brand: "var(--brand)",
        caution: "var(--caution)",
        danger: "var(--danger)",
        brass: "var(--brass)",
      },
      fontSize: {
        caption: "var(--t-caption)",
        footnote: "var(--t-footnote)",
        subhead: "var(--t-subhead)",
        callout: "var(--t-callout)",
        body: "var(--t-body)",
        "title-3": "var(--t-title-3)",
        "title-2": "var(--t-title-2)",
        "title-1": "var(--t-title-1)",
        display: "var(--t-display)",
      },
      borderRadius: {
        s: "var(--radius-s)",
        m: "var(--radius-m)",
        l: "var(--radius-l)",
      },
      boxShadow: {
        1: "var(--lift-1)",
        2: "var(--lift-2)",
        3: "var(--lift-3)",
      },
    },
  },
  plugins: [],
} satisfies Config;
