import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        canvas: '#F6F7F9',
        surface: '#FFFFFF',
        border: {
          DEFAULT: '#E4E7EC',
          strong: '#D0D5DD',
        },
        ink: {
          DEFAULT: '#101828',
          muted: '#475467',
          faint: '#98A2B3',
        },
        brand: {
          50: '#EFF4FA',
          100: '#DCE6F2',
          500: '#1E3A5F',
          600: '#16304F',
          700: '#0F2540',
        },
        status: {
          matchBg: '#E7F6EF', matchFg: '#0F7A57', matchBorder: '#B7E4CF',
          partialBg: '#EAF1FE', partialFg: '#1D4ED8', partialBorder: '#C7DAFB',
          reviewBg: '#FEF3E2', reviewFg: '#B45309', reviewBorder: '#FBDFAE',
          dangerBg: '#FEEBEC', dangerFg: '#B42318', dangerBorder: '#F7C6C4',
          dupBg: '#F4EBFF', dupFg: '#6941C6', dupBorder: '#E3D2FC',
          neutralBg: '#F2F4F7', neutralFg: '#475467', neutralBorder: '#E4E7EC',
        },
      },
      boxShadow: {
        card: '0 1px 2px 0 rgba(16, 24, 40, 0.04)',
        drawer: '-4px 0 24px 0 rgba(16, 24, 40, 0.08)',
      },
      borderRadius: {
        md: '8px',
        lg: '10px',
      },
    },
  },
  plugins: [],
} satisfies Config
