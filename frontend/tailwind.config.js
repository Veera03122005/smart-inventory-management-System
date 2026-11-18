/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Preserved legacy tokens for full backward compatibility
        ink: { DEFAULT: "#16211c", soft: "#24332b", mute: "#5b6b62" },
        leaf: { DEFAULT: "#1f6f4a", dark: "#17553a", light: "#e6f2ec" },
        spice: { DEFAULT: "#d97706", light: "#fdf3e1" },
        paper: "#f6f5f1",

        // Semantic Design Tokens (Precision Kitchen Utility)
        brand: {
          50: "#ecfdf5",
          100: "#d1fae5",
          200: "#a7f3d0",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          800: "#065f46",
          900: "#064e3b",
        },
        surface: {
          canvas: "#f8fafc",
          card: "#ffffff",
          muted: "#f1f5f9",
          border: "#e2e8f0",
          hover: "#f8fafc",
        },
        content: {
          primary: "#0f172a",
          secondary: "#334155",
          muted: "#64748b",
          subtle: "#94a3b8",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(15, 23, 42, 0.05), 0 1px 2px -1px rgba(15, 23, 42, 0.05)",
        hover: "0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.07)",
        elevated: "0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04)",
      },
    },
  },
  plugins: [],
};
