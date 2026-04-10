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

export async function fetchRetargetLeads(): Promise<LeadListResponse> {
  const res = await apiFetch('/api/v1/retarget')
  if (!res.ok) await parseError(res)
  return res.json()
}

export function useRetargetQuery() {
  return useQuery({
    queryKey: ['retarget', 'leads'],
    queryFn: fetchRetargetLeads,
  })
}
