/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Dark finance palette
        surface: {
          DEFAULT: "#0d0f14",   // deep background
          raised:  "#13161e",   // card background
          border:  "#1e2330",   // subtle borders
          hover:   "#1a1e2a",   // hover states
        },
        accent: {
          DEFAULT: "#00d4aa",   // teal-green — primary CTA, positive returns
          dim:     "#00d4aa22", // faint accent background
          hover:   "#00b894",   // darker on hover
        },
        loss:     "#ff4d6a",    // red for negative returns
        lossDim:  "#ff4d6a22",
        gain:     "#00d4aa",
        gainDim:  "#00d4aa22",
        text: {
          primary:   "#e8eaf0",
          secondary: "#8892a4",
          muted:     "#4a5568",
        },
      },
      fontFamily: {
        sans:  ["Inter", "system-ui", "sans-serif"],
        mono:  ["JetBrains Mono", "monospace"],
      },
      borderRadius: {
        card: "12px",
      },
      boxShadow: {
        card:  "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(30,35,48,0.8)",
        glow:  "0 0 20px rgba(0,212,170,0.15)",
      },
    },
  },
  plugins: [],
}
