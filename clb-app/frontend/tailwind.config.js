/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        debt: "#EF4444",
        recovery: "#22C55E",
        warning: "#EAB308",
        neutral: "#3B82F6"
      }
    }
  },
  plugins: []
};
