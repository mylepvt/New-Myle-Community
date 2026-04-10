import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type FollowUpPublic = {
  id: number
  lead_id: number
  lead_name: string
  note: string
  due_at: string | null
  completed_at: string | null
  created_by_user_id: number
  created_at: string
}

export type FollowUpListResponse = {
  items: FollowUpPublic[]
  total: number
  limit: number
  offset: number
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

function qs(openOnly: boolean): string {
  const p = new URLSearchParams()
  if (!openOnly) p.set('open_only', 'false')
  const s = p.toString()
  return s ? `?${s}` : ''
}

export async function fetchFollowUps(openOnly: boolean): Promise<FollowUpListResponse> {
  const res = await apiFetch(`/api/v1/follow-ups${qs(openOnly)}`)
  if (!res.ok) await parseError(res)
  return res.json()
}

export async function createFollowUp(body: {
  lead_id: number
  note: string
  due_at?: string | null
}): Promise<FollowUpPublic> {
  const res = await apiFetch('/api/v1/follow-ups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

export async function patchFollowUp(
  id: number,
  body: { note?: string; due_at?: string | null; completed?: boolean },
): Promise<FollowUpPublic> {
  const res = await apiFetch(`/api/v1/follow-ups/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

export async function deleteFollowUp(id: number): Promise<void> {
  const res = await apiFetch(`/api/v1/follow-ups/${id}`, { method: 'DELETE' })
  if (!res.ok) await parseError(res)
}

export function useFollowUpsQuery(openOnly: boolean) {
  return useQuery({
    queryKey: ['follow-ups', 'list', openOnly],
    queryFn: () => fetchFollowUps(openOnly),
  })
}

export function useCreateFollowUpMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createFollowUp,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['follow-ups'] }),
  })
}

export function usePatchFollowUpMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { id: number; body: Parameters<typeof patchFollowUp>[1] }) =>
      patchFollowUp(args.id, args.body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['follow-ups'] }),
  })
}

export function useDeleteFollowUpMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteFollowUp,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['follow-ups'] }),
  })
}
