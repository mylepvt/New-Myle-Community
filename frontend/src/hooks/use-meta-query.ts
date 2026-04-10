import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type MetaResponse = {
  name: string
  api_version: number
  environment: string
  features: {
    intelligence: boolean
  }
}

/** Optimistic default before `/meta` loads — matches typical dev backend. */
export const DEFAULT_META: MetaResponse = {
  name: 'myle-vl2',
  api_version: 1,
  environment: 'development',
  features: { intelligence: true },
}

export async function fetchMeta(): Promise<MetaResponse> {
  const res = await apiFetch('/api/v1/meta')
  if (!res.ok) {
    throw new Error(`Meta HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Bootstrap payload for a smart shell: feature flags + environment (cache long; invalidates rarely).
 */
export function useMetaQuery(enabled = true) {
  return useQuery({
    queryKey: ['meta', 'bootstrap'],
    queryFn: fetchMeta,
    enabled,
    staleTime: 5 * 60_000,
    retry: 2,
    placeholderData: DEFAULT_META,
  })
}
