import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        ink: '#111827',
        line: '#d7dde8',
        paper: '#f7f8fb',
        signal: '#2563eb',
        mint: '#0f9f7a',
        coral: '#db5b4f',
      },
      boxShadow: {
        panel: '0 18px 50px rgba(17, 24, 39, 0.08)',
      },
    },
  },
  plugins: [],
}

export default config
