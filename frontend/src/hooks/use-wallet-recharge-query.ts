import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type WalletRecharge = {
  id: number
  user_id: number
  amount_cents: number
  utr_number: string | null
  proof_url: string | null
  status: string
  admin_note: string | null
  reviewed_by_user_id: number | null
  reviewed_at: string | null
  created_at: string
}

export type WalletRechargeCreate = {
  amount_cents: number
  utr_number?: string
  proof_url?: string
  idempotency_key?: string
}

export type WalletRechargeListResponse = {
  items: WalletRecharge[]
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

async function fetchRechargeRequests(): Promise<WalletRechargeListResponse> {
  const res = await apiFetch('/api/v1/wallet/recharge-requests')
  if (!res.ok) await parseError(res)
  return res.json()
}

async function postRechargeRequest(body: WalletRechargeCreate): Promise<WalletRecharge> {
  const res = await apiFetch('/api/v1/wallet/recharge-requests', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

async function patchRechargeRequest(
  id: number,
  body: { status: 'approved' | 'rejected'; admin_note?: string },
): Promise<WalletRecharge> {
  const res = await apiFetch(`/api/v1/wallet/recharge-requests/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

function invalidateRechargeAndWallet(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['wallet-recharge-requests'] })
  void qc.invalidateQueries({ queryKey: ['wallet'] })
}

export function useWalletRechargeRequestsQuery() {
  return useQuery({
    queryKey: ['wallet-recharge-requests'],
    queryFn: fetchRechargeRequests,
  })
}

export function useCreateRechargeRequestMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: postRechargeRequest,
    onSuccess: () => invalidateRechargeAndWallet(qc),
  })
}

export function useReviewRechargeRequestMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number
      body: { status: 'approved' | 'rejected'; admin_note?: string }
    }) => patchRechargeRequest(id, body),
    onSuccess: () => invalidateRechargeAndWallet(qc),
  })
}
