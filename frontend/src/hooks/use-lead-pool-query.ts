import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'
import type { LeadListResponse } from '@/hooks/use-leads-query'

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

async function fetchLeadPool(): Promise<LeadListResponse> {
  const res = await apiFetch('/api/v1/lead-pool')
  if (!res.ok) {
    await parseError(res)
  }
  return res.json()
}

export function useLeadPoolQuery(enabled = true) {
  return useQuery({
    queryKey: ['lead-pool'],
    queryFn: fetchLeadPool,
    enabled,
  })
}
