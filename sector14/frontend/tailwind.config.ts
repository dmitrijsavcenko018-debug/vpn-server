import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/app/**/*.{ts,tsx}", "./src/components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#05070d",
        surface: "#0d1322",
        accent: "#4f7dff",
        muted: "#9aa7c7"
      }
    }
  },
  plugins: []
};

export default config;
