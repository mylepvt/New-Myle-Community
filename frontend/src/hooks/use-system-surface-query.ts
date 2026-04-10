import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type SystemSurface = 'training' | 'decision-engine' | 'coaching'

export type SystemStubResponse = {
  items: Record<string, unknown>[]
  total: number
  note: string | null
}

const PATHS: Record<SystemSurface, string> = {
  training: '/api/v1/system/training',
  'decision-engine': '/api/v1/system/decision-engine',
  coaching: '/api/v1/system/coaching',
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

async function fetchSystemSurface(surface: SystemSurface): Promise<SystemStubResponse> {
  const res = await apiFetch(PATHS[surface])
  if (!res.ok) await parseError(res)
  return res.json()
}

export function useSystemSurfaceQuery(surface: SystemSurface, enabled = true) {
  return useQuery({
    queryKey: ['system', surface],
    queryFn: () => fetchSystemSurface(surface),
    enabled,
  })
}
