/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#1a1a2e',
        'bg-secondary': '#16213e',
        'bg-tertiary': '#0f3460',
        'text-primary': '#e8e8e8',
        'text-secondary': '#a0a0b0',
        'text-muted': '#6c6c7e',
        'accent-blue': '#378ADD',
        'flag-green': '#4ade80',
        'flag-yellow': '#facc15',
        'flag-red': '#ef4444',
      },
    },
  },
  plugins: [],
}
