/**
 * English-only strings hub — add locales later without rewiring every component.
 * Roadmap Phase 7: swap `DEFAULT_LOCALE` / load JSON when product picks languages.
 */
export type Locale = 'en'

export const DEFAULT_LOCALE: Locale = 'en'

const STRINGS = {
  en: {
    appTitle: 'Myle',
    appTagline: 'Pipeline, follow-ups, and team leads in one place.',
  },
} as const

export type StringKey = keyof typeof STRINGS.en

export function t(key: StringKey, _locale: Locale = DEFAULT_LOCALE): string {
  return STRINGS[_locale][key]
}
