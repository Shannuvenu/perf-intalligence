/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0d12",
        panel: "#12161d",
        panel2: "#171c25",
        border: "#232935",
        text: "#e6e9ef",
        subtext: "#8993a4",
        accent: "#4f8cff",
        good: "#34c283",
        warn: "#e0a83e",
        crit: "#f0564d",
      },
      fontFamily: {
        mono: ["ui-monospace", "SF Mono", "Cascadia Mono", "Roboto Mono", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
