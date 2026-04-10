import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type LeadPublic = {
  id: number
  name: string
}

export type LeadListResponse = {
  items: LeadPublic[]
  total: number
}

async function fetchLeads(): Promise<LeadListResponse> {
  const res = await apiFetch('/api/v1/leads')
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const msg =
      typeof err === 'object' && err !== null && 'error' in err
        ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
        : res.statusText
    throw new Error(msg || `HTTP ${res.status}`)
  }
  return res.json()
}

export function useLeadsQuery(enabled: boolean) {
  return useQuery({
    queryKey: ['leads', 'list'],
    queryFn: fetchLeads,
    enabled,
  })
}
