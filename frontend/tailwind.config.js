import tailwindcssAnimate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'sans-serif',
        ],
        heading: ['Poppins', 'Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'ds-h1': [
          '1.5rem',
          { lineHeight: '2rem', fontWeight: '600', letterSpacing: '-0.02em' },
        ],
        'ds-h2': [
          '1.25rem',
          { lineHeight: '1.75rem', fontWeight: '600', letterSpacing: '-0.015em' },
        ],
        'ds-h3': [
          '1rem',
          { lineHeight: '1.5rem', fontWeight: '500', letterSpacing: '-0.01em' },
        ],
        'ds-body': [
          '0.875rem',
          { lineHeight: '1.375rem', fontWeight: '400' },
        ],
        'ds-caption': [
          '0.75rem',
          { lineHeight: '1rem', fontWeight: '400' },
        ],
      },
      spacing: {
        'ds-1': '4px',
        'ds-2': '8px',
        'ds-3': '16px',
        'ds-4': '24px',
        'ds-5': '32px',
      },
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        surface: 'hsl(var(--surface))',
        subtle: 'hsl(var(--subtle))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        xl: 'calc(var(--radius) + 4px)',
      },
      letterSpacing: {
        'label-wide': '0.08em',
      },
      boxShadow: {
        'glass-glow':
          '0 0 40px -12px hsl(344 68% 48% / 0.30), inset 0 1px 0 0 hsl(0 0% 100% / 0.06)',
        'glass-inset':
          'inset 0 1px 2px rgba(0,0,0,0.2), inset 0 -1px 0 rgba(255,255,255,0.03)',
        'sidebar-glow':
          'inset -1px 0 0 hsl(344 50% 42% / 0.14)',
        'header-bar':
          '0 1px 0 0 hsl(344 38% 32% / 0.18), 0 12px 40px -16px rgba(0,0,0,0.5)',
      },
    },
  },
  plugins: [tailwindcssAnimate],
}
