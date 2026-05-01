/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        tibia: {
          darkgreen: '#1a3a1a',
          green: '#2d5016',
          lightgreen: '#3d6b1f',
          gold: '#c6a664',
          lightgold: '#e0c891',
          brown: '#3d2817',
          darkbrown: '#2a1810',
          red: '#8b0000',
          blue: '#1e3a8a',
        }
      },
      fontFamily: {
        tibia: ['"Press Start 2P"', 'cursive'],
      }
    },
  },
  plugins: [],
}
