import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type AnalyticsSurface = 'activity-log' | 'day-2-report'

export type AnalyticsStubResponse = {
  items: Record<string, unknown>[]
  total: number
  note: string | null
}

const PATHS: Record<AnalyticsSurface, string> = {
  'activity-log': '/api/v1/analytics/activity-log',
  'day-2-report': '/api/v1/analytics/day-2-report',
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

async function fetchAnalyticsSurface(surface: AnalyticsSurface): Promise<AnalyticsStubResponse> {
  const res = await apiFetch(PATHS[surface])
  if (!res.ok) await parseError(res)
  return res.json()
}

export function useAnalyticsSurfaceQuery(surface: AnalyticsSurface, enabled = true) {
  return useQuery({
    queryKey: ['analytics', surface],
    queryFn: () => fetchAnalyticsSurface(surface),
    enabled,
  })
}
