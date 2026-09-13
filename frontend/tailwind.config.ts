import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0b1120",
        surface: "#111827",
        border: "#1f2937",
        foreground: "#e2e8f0",
        muted: "#94a3b8",
        accent: "#38bdf8",
        success: "#34d399",
        danger: "#f87171",
        warning: "#fbbf24",
      },
    },
  },
  plugins: [],
};

export default config;
