/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', './tests/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#18212f',
        steel: '#526072',
        line: '#d8dee7',
        panel: '#f7f9fb',
        amberRisk: '#b45309',
        redRisk: '#b91c1c',
        greenRisk: '#047857',
      },
    },
  },
  plugins: [],
};
