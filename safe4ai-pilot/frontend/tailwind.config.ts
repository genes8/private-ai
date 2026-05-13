import type { Config } from "tailwindcss";

const tokens = {
  colors: {
    ink:    { DEFAULT: "#0b0d10", 2: "#16191e", 3: "#232730", 4: "#353a44" },
    paper:  { DEFAULT: "#fafaf7", 2: "#f4f1ea", 3: "#ebe7dd" },
    surface:{ DEFAULT: "#ffffff", 2: "#f7f5f0" },
    line:   { DEFAULT: "#e7e3d8", 2: "#d6dde6", 3: "#c2c8d2" },
    text:   { DEFAULT: "#14161a", 2: "#4a4f57", 3: "#7c8290", mute: "#9aa1ac" },
    slate:  { DEFAULT: "#7c8aa0", 2: "#a8b0bd", 3: "#c4cad4" },
    accent: { DEFAULT: "#3b6cf2", 2: "#2a55d4", soft: "#eaf0ff", tint: "#f4f7ff" },
    success:{ DEFAULT: "#2f8f5e", soft: "#e6f3ec" },
    warn:   { DEFAULT: "#b87a1a", soft: "#f9efd9" },
    danger: { DEFAULT: "#c0392b", soft: "#fbe9e6" },
  },
  fontFamily: {
    sans:  ['"Geist"', "ui-sans-serif", "system-ui", "sans-serif"],
    mono:  ['"Geist Mono"', "ui-monospace", "SF Mono", "Menlo", "monospace"],
    serif: ['"Instrument Serif"', "Georgia", "serif"],
  },
  borderRadius: {
    sm: "4px",
    DEFAULT: "6px",
    lg: "10px",
    xl: "14px",
  },
  boxShadow: {
    sm:  "0 1px 0 rgba(20,22,26,.04), 0 1px 2px rgba(20,22,26,.05)",
    DEFAULT: "0 1px 0 rgba(20,22,26,.04), 0 4px 12px rgba(20,22,26,.06), 0 1px 2px rgba(20,22,26,.04)",
    pop: "0 1px 0 rgba(255,255,255,.6) inset, 0 12px 40px rgba(20,22,26,.16), 0 0 0 .5px rgba(20,22,26,.08)",
  },
  letterSpacing: {
    tight:  "-0.02em",
    snug:   "-0.012em",
    body:   "-0.005em",
    kicker: "0.08em",
  },
} as const;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: tokens },
} satisfies Config;
