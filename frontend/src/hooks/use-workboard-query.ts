import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'
import type { LeadPublic } from '@/hooks/use-leads-query'

export type WorkboardColumn = {
  status: string
  total: number
  items: LeadPublic[]
}

export type WorkboardResponse = {
  columns: WorkboardColumn[]
  max_rows_fetched: number
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

export async function fetchWorkboard(): Promise<WorkboardResponse> {
  const res = await apiFetch('/api/v1/workboard')
  if (!res.ok) {
    await parseError(res)
  }
  return res.json()
}

export function useWorkboardQuery(enabled: boolean) {
  return useQuery({
    queryKey: ['workboard'],
    queryFn: fetchWorkboard,
    enabled,
  })
}
