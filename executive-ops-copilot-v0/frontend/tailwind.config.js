/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', './tests/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#161a22',
        steel: '#5d6673',
        line: '#d7dbe2',
        panel: '#f6f7f9',
        brand: '#3d4654',
        brandDark: '#202734',
        brandSoft: '#eef0f4',
        glass: 'rgba(255,255,255,0.72)',
        amberRisk: '#b45309',
        redRisk: '#b91c1c',
        greenRisk: '#047857',
      },
    },
  },
  plugins: [],
};
