/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Noto Sans", "Noto Sans Bengali", "system-ui", "sans-serif"],
      },
      colors: {
        // Home Risk Score classes (SPEC §8)
        risk: { low: "#1a9850", moderate: "#fee08b", high: "#f46d43", severe: "#a50026" },
      },
    },
  },
  plugins: [],
};
