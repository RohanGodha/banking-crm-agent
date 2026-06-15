import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // Inspired by enterprise BFSI dashboards — restrained zinc-slate base,
        // electric blue accent for primary actions and live events.
        bg:        { DEFAULT: '#0a0d12', soft: '#0f131a', card: '#141923' },
        border:    { DEFAULT: '#1f2733', strong: '#2a3344' },
        text:      { DEFAULT: '#e5e7eb', muted: '#9aa3af', dim: '#6b7280' },
        accent:    { DEFAULT: '#3b82f6', soft: '#1e40af', glow: '#60a5fa' },
        positive:  { DEFAULT: '#10b981' },
        warning:   { DEFAULT: '#f59e0b' },
        danger:    { DEFAULT: '#ef4444' },
      },
      keyframes: {
        'fade-in': { from: { opacity: '0', transform: 'translateY(2px)' }, to: { opacity: '1', transform: 'none' } },
        'pulse-dot': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.4' } },
      },
      animation: {
        'fade-in': 'fade-in 180ms ease-out',
        'pulse-dot': 'pulse-dot 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
