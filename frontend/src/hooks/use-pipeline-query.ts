import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type PipelineLead = {
  id: number
  name: string
  phone?: string
  email?: string
  city?: string
  status: string
  created_at: string
  assigned_to_user_id?: number
  payment_status?: string
  call_status?: string
}

export type PipelineView = {
  columns: string[]
  leads_by_status: Record<string, PipelineLead[]>
  total_leads: number
  conversion_rate: number
  user_role: string
  status_labels: Record<string, string>
}

export type PipelineMetrics = {
  period: string
  status_counts: Record<string, number>
  total_leads: number
  conversion_rate: number
  payment_rate: number
  day1_rate: number
  day2_rate: number
  funnel: {
    new_leads: number
    contacted: number
    paid: number
    day1: number
    day2: number
    converted: number
  }
}

export async function fetchPipelineView(): Promise<PipelineView> {
  const res = await apiFetch('/api/v1/pipeline/view')
  if (!res.ok) {
    throw new Error(`Pipeline view HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchPipelineMetrics(days = 30): Promise<PipelineMetrics> {
  const res = await apiFetch(`/api/v1/pipeline/metrics?days=${days}`)
  if (!res.ok) {
    throw new Error(`Pipeline metrics HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchAvailableTransitions(leadId: number): Promise<string[]> {
  const res = await apiFetch(`/api/v1/pipeline/leads/${leadId}/transitions`)
  if (!res.ok) {
    throw new Error(`Available transitions HTTP ${res.status}`)
  }
  return res.json()
}

export async function transitionLeadStatus(
  leadId: number,
  targetStatus: string,
  notes?: string
): Promise<{ success: boolean; message: string; new_status: string }> {
  const res = await apiFetch('/api/v1/pipeline/transition', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lead_id: leadId,
      target_status: targetStatus,
      notes,
    }),
  })
  if (!res.ok) {
    throw new Error(`Lead transition HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchPipelineStatuses(): Promise<Record<string, string>> {
  const res = await apiFetch('/api/v1/pipeline/statuses')
  if (!res.ok) {
    throw new Error(`Pipeline statuses HTTP ${res.status}`)
  }
  return res.json()
}

export async function autoExpireLeads(): Promise<{ expired_count: number }> {
  const res = await apiFetch('/api/v1/pipeline/auto-expire', {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Auto expire HTTP ${res.status}`)
  }
  return res.json()
}

export function usePipelineViewQuery() {
  return useQuery({
    queryKey: ['pipeline', 'view'],
    queryFn: fetchPipelineView,
    staleTime: 30_000,
  })
}

export function usePipelineMetricsQuery(days = 30) {
  return useQuery({
    queryKey: ['pipeline', 'metrics', days],
    queryFn: () => fetchPipelineMetrics(days),
    staleTime: 60_000,
  })
}

export function useAvailableTransitionsQuery(leadId: number) {
  return useQuery({
    queryKey: ['pipeline', 'transitions', leadId],
    queryFn: () => fetchAvailableTransitions(leadId),
    staleTime: 30_000,
    enabled: !!leadId,
  })
}

export function useTransitionLeadMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ leadId, targetStatus, notes }: {
      leadId: number
      targetStatus: string
      notes?: string
    }) => transitionLeadStatus(leadId, targetStatus, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
      queryClient.invalidateQueries({ queryKey: ['leads'] })
    },
  })
}

export function useAutoExpireMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: autoExpireLeads,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
      queryClient.invalidateQueries({ queryKey: ['leads'] })
    },
  })
}

export function usePipelineStatusesQuery() {
  return useQuery({
    queryKey: ['pipeline', 'statuses'],
    queryFn: fetchPipelineStatuses,
    staleTime: 300_000, // Cache for 5 minutes
  })
}
