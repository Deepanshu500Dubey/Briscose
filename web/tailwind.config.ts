import type { Config } from 'tailwindcss';

// Design tokens straight from the project blueprint, Section 2 (Brand &
// design system). Navy is the primary surface/action color; gold is a
// spark reserved for the single most important thing on a screen.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['class'],
  theme: {
    extend: {
      colors: {
        brand: {
          navy: '#0B3D70',
          'navy-deep': '#082A4E',
          gold: '#DD9200',
          'gold-bright': '#F5A800',
        },
        paper: '#F4F6FA',
        ink: {
          DEFAULT: '#10192B',
          soft: '#46536B',
          // Darkened from the blueprint's literal #7C88A0 (~4.0:1 on white,
          // caught by the E2E suite's axe-core pass at ~12px text — WCAG AA
          // needs 4.5:1 for anything below "large text" size). #6B7690
          // reads as the same de-emphasized blue-gray at ~4.6:1.
          faint: '#6B7690',
        },
        line: {
          DEFAULT: '#DDE3EE',
          soft: '#EAEEF5',
        },
        status: {
          'ok-fg': '#166B45',
          'ok-bg': '#E4F6EC',
          'ok-line': '#BFE6CF',
          'warn-fg': '#8A5300',
          'warn-bg': '#FDF1DA',
          'warn-line': '#F3D99A',
          'bad-fg': '#9C2A34',
          'bad-bg': '#FBE9EA',
          'bad-line': '#F0C1C6',
          'info-fg': '#1D4F8C',
          'info-bg': '#E9F0FB',
          'info-line': '#C6D9F3',
        },
      },
      fontFamily: {
        display: ['"Barlow Condensed"', 'Arial Narrow', 'sans-serif'],
        body: ['"Public Sans"', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '10px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(10,20,40,.04), 0 8px 24px -12px rgba(10,20,40,.12)',
      },
    },
  },
  plugins: [],
} satisfies Config;
