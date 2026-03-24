import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        bg: "#070A10",
        surface: "#111522",
        accent: "#4F7DFF",
        textSoft: "#B2BCD6"
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(79,125,255,0.2), 0 20px 40px rgba(7,10,16,0.6)"
      }
    }
  },
  plugins: []
};

export default config;
