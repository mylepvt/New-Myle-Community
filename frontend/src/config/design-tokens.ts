/**
 * Design system tokens — single source of truth for names (Tailwind maps via CSS variables).
 * Colors match hex spec; do not use arbitrary one-off hex in components — use semantic classes.
 */
export const designTokens = {
  color: {
    canvas: '#0B0F14',
    surface: '#121821',
    card: '#1A2230',
    textPrimary: '#E6EDF3',
    textSecondary: '#9AA4B2',
    textMuted: '#6B7280',
    accent: '#4F46E5',
    success: '#22C55E',
    warning: '#F59E0B',
    danger: '#EF4444',
  },
  font: {
    ui: 'Inter',
    heading: 'Poppins',
  },
  type: {
    h1: { px: 24, weight: 600 as const },
    h2: { px: 20, weight: 600 as const },
    h3: { px: 16, weight: 500 as const },
    body: { px: 14, weight: 400 as const },
    caption: { px: 12, weight: 400 as const },
  },
  space: {
    micro: 4,
    tight: 8,
    standard: 16,
    section: 24,
    block: 32,
  },
  radius: {
    card: 12,
    control: 8,
  },
  control: {
    inputHeight: 40,
  },
} as const
