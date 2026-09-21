/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#ffffff",
        panel: "#ffffff",
        panel2: "#f4f4f5",
        border: "#dcdcdf",
        text: "#0a0a0a",
        subtext: "#6b6b70",
        accent: "#000000",
        good: "#1a7f4b",
        warn: "#a5680a",
        crit: "#c02b26",
      },
      fontFamily: {
        mono: ["ui-monospace", "SF Mono", "Cascadia Mono", "Roboto Mono", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
