/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "var(--bg-base)",
          surface: "var(--bg-surface)",
          elevated: "var(--bg-elevated)",
          overlay: "var(--bg-overlay)",
        },
        border: {
          subtle: "var(--border-subtle)",
          muted: "var(--border-muted)",
          active: "var(--border-active)",
        },
        brand: {
          blue: "var(--brand-blue)",
          dim: "var(--brand-blue-dim)",
          glow: "var(--brand-glow)",
        },
        bull: { DEFAULT: "var(--bull-green)", dim: "var(--bull-dim)" },
        bear: { DEFAULT: "var(--bear-red)", dim: "var(--bear-dim)" },
        amber: { DEFAULT: "var(--neutral-amber)", dim: "var(--neutral-amber-dim)" },
        halt: "var(--halt-red)",
        breakeven: "var(--breakeven)",
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
          inverse: "var(--text-inverse)",
        },
      },
      fontFamily: {
        display: ['"Space Mono"', "monospace"],
        sans: ['Geist', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      maxWidth: {
        "screen-2xl": "1536px",
      },
      keyframes: {
        "data-flash": {
          "0%": { backgroundColor: "var(--brand-glow)" },
          "100%": { backgroundColor: "transparent" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.3" },
        },
        "blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        "slide-in": {
          "0%": { opacity: "0", transform: "translateX(1rem)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        "data-flash": "data-flash 400ms ease-out",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
        "blink": "blink 1s step-end infinite",
        "slide-in": "slide-in 200ms ease-out",
      },
    },
  },
  plugins: [],
}
