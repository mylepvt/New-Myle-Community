import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type LeadDetail = {
  id: number
  name: string
  status: string
  phone: string | null
  email: string | null
  city: string | null
  source: string | null
  notes: string | null
  call_status: string | null
  call_count: number
  last_called_at: string | null
  whatsapp_sent_at: string | null
  assigned_to_user_id: number | null
  payment_status: string | null
  payment_amount_cents: number | null
  payment_proof_url: string | null
  payment_proof_uploaded_at: string | null
  day1_completed_at: string | null
  day2_completed_at: string | null
  day3_completed_at: string | null
  created_by_user_id: number
  created_at: string
  archived_at: string | null
  in_pool: boolean
}

export type CallEvent = {
  id: number
  lead_id: number
  user_id: number
  outcome: string
  duration_seconds: number | null
  notes: string | null
  called_at: string
  created_at: string
}

export type CallEventCreate = {
  outcome: string
  duration_seconds?: number
  notes?: string
}

export type CallEventsListResponse = {
  items: CallEvent[]
  total: number
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

async function fetchLeadDetail(leadId: number): Promise<LeadDetail> {
  const res = await apiFetch(`/api/v1/leads/${leadId}`)
  if (!res.ok) await parseError(res)
  return res.json()
}

async function fetchLeadCalls(leadId: number): Promise<CallEventsListResponse> {
  const res = await apiFetch(`/api/v1/leads/${leadId}/calls`)
  if (!res.ok) await parseError(res)
  return res.json()
}

async function postLeadCall(leadId: number, body: CallEventCreate): Promise<CallEvent> {
  const res = await apiFetch(`/api/v1/leads/${leadId}/calls`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

async function patchLeadDetail(
  leadId: number,
  body: Partial<LeadDetail>,
): Promise<LeadDetail> {
  const res = await apiFetch(`/api/v1/leads/${leadId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

export function useLeadDetailQuery(leadId: number) {
  return useQuery({
    queryKey: ['lead-detail', leadId],
    queryFn: () => fetchLeadDetail(leadId),
    enabled: leadId > 0,
  })
}

export function useLeadCallsQuery(leadId: number) {
  return useQuery({
    queryKey: ['lead-calls', leadId],
    queryFn: () => fetchLeadCalls(leadId),
    enabled: leadId > 0,
  })
}

export function useLogCallMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ leadId, body }: { leadId: number; body: CallEventCreate }) =>
      postLeadCall(leadId, body),
    onSuccess: (_data, { leadId }) => {
      void qc.invalidateQueries({ queryKey: ['lead-detail', leadId] })
      void qc.invalidateQueries({ queryKey: ['lead-calls', leadId] })
    },
  })
}

export function usePatchLeadDetailMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ leadId, body }: { leadId: number; body: Partial<LeadDetail> }) =>
      patchLeadDetail(leadId, body),
    onSuccess: (_data, { leadId }) => {
      void qc.invalidateQueries({ queryKey: ['lead-detail', leadId] })
      void qc.invalidateQueries({ queryKey: ['leads', 'list'] })
    },
  })
}
