/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#f5f1eb',
        'bg-secondary': '#ffffff',
        'bg-tertiary': '#e4dfd8',
        'text-primary': '#2a1a18',
        'text-secondary': '#6b5f58',
        'text-muted': '#b0a89e',
        'accent-blue': '#5c1020',
        'flag-green': '#1D9E75',
        'flag-yellow': '#BA7517',
        'flag-red': '#A32D2D',
      },
    },
  },
  plugins: [],
}
