/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#16211c", soft: "#24332b", mute: "#5b6b62" },
        leaf: { DEFAULT: "#1f6f4a", dark: "#17553a", light: "#e6f2ec" },
        spice: { DEFAULT: "#d97706", light: "#fdf3e1" },
        paper: "#f6f5f1",
      },
      fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
