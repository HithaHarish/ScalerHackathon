/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 2px 8px rgb(0 0 0 / 0.04), 0 1px 3px rgb(0 0 0 / 0.02)',
        'float': '0 8px 30px rgb(0 0 0 / 0.04), 0 4px 10px rgb(0 0 0 / 0.02)',
      },
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
