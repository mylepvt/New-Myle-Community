import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'won' | 'lost'

export const LEAD_STATUS_OPTIONS: { value: LeadStatus; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

export type LeadPublic = {
  id: number
  name: string
  status: string
  created_by_user_id: number
  created_at: string
  archived_at: string | null
  deleted_at: string | null
  in_pool: boolean
}

export type LeadListResponse = {
  items: LeadPublic[]
  total: number
  limit: number
  offset: number
}

export type LeadListFilters = {
  q: string
  status: '' | LeadStatus
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

export type LeadsListMode = 'active' | 'archived' | 'recycle'

function buildLeadsQueryString(filters: LeadListFilters, listMode: LeadsListMode): string {
  const p = new URLSearchParams()
  const t = filters.q.trim()
  if (t) p.set('q', t)
  if (filters.status) p.set('status', filters.status)
  if (listMode === 'archived') p.set('archived_only', 'true')
  if (listMode === 'recycle') p.set('deleted_only', 'true')
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}

async function fetchLeads(
  filters: LeadListFilters,
  listMode: LeadsListMode,
): Promise<LeadListResponse> {
  const res = await apiFetch(`/api/v1/leads${buildLeadsQueryString(filters, listMode)}`)
  if (!res.ok) {
    await parseError(res)
  }
  return res.json()
}

export async function createLead(name: string, status: LeadStatus = 'new'): Promise<LeadPublic> {
  const res = await apiFetch('/api/v1/leads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, status }),
  })
  if (!res.ok) {
    await parseError(res)
  }
  return res.json()
}

export async function patchLead(
  id: number,
  body: {
    name?: string
    status?: LeadStatus
    archived?: boolean
    in_pool?: boolean
    restored?: boolean
  },
): Promise<LeadPublic> {
  const res = await apiFetch(`/api/v1/leads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    await parseError(res)
  }
  return res.json()
}

export async function deleteLead(id: number): Promise<void> {
  const res = await apiFetch(`/api/v1/leads/${id}`, { method: 'DELETE' })
  if (!res.ok) {
    await parseError(res)
  }
}

export async function claimLead(id: number): Promise<LeadPublic> {
  const res = await apiFetch(`/api/v1/leads/${id}/claim`, { method: 'POST' })
  if (!res.ok) {
    await parseError(res)
  }
  return res.json()
}

export function useLeadsQuery(
  enabled: boolean,
  filters: LeadListFilters,
  listMode: LeadsListMode = 'active',
) {
  return useQuery({
    queryKey: ['leads', 'list', listMode, filters.q.trim(), filters.status],
    queryFn: () => fetchLeads(filters, listMode),
    enabled,
  })
}

function invalidateLeadRelated(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['leads', 'list'] })
  void qc.invalidateQueries({ queryKey: ['lead-pool'] })
  void qc.invalidateQueries({ queryKey: ['workboard'] })
  void qc.invalidateQueries({ queryKey: ['retarget'] })
}

export function useCreateLeadMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, status }: { name: string; status?: LeadStatus }) =>
      createLead(name, status ?? 'new'),
    onSuccess: () => invalidateLeadRelated(qc),
  })
}

export function usePatchLeadMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number
      body: {
        name?: string
        status?: LeadStatus
        archived?: boolean
        in_pool?: boolean
        restored?: boolean
      }
    }) => patchLead(id, body),
    onSuccess: () => invalidateLeadRelated(qc),
  })
}

export function useDeleteLeadMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteLead,
    onSuccess: () => invalidateLeadRelated(qc),
  })
}

export function useClaimLeadMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: claimLead,
    onSuccess: () => invalidateLeadRelated(qc),
  })
}
