/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', './tests/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0f1f3d',
        steel: '#52647a',
        line: '#d8e2ef',
        panel: '#f6f9fd',
        brand: '#1455d9',
        brandDark: '#0b367f',
        brandSoft: '#e8f1ff',
        amberRisk: '#b45309',
        redRisk: '#b91c1c',
        greenRisk: '#047857',
      },
    },
  },
  plugins: [],
};
