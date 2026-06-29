/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: '#0c0c14', card: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.08)' },
        accent: { cyan: '#22d3ee', violet: '#a78bfa', pink: '#f472b6' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      animation: { pulse_slow: 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite', glow: 'glow 2s ease-in-out infinite alternate' },
      keyframes: { glow: { from: { boxShadow: '0 0 20px rgba(34,211,238,0.15)' }, to: { boxShadow: '0 0 30px rgba(167,139,250,0.25)' } } },
    },
  },
  plugins: [],
}
