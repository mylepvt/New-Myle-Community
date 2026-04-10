import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type WalletLedgerEntryPublic = {
  id: number
  user_id: number
  amount_cents: number
  currency: string
  note: string | null
  created_at: string
}

export type WalletSummaryResponse = {
  balance_cents: number
  currency: string
  recent_entries: WalletLedgerEntryPublic[]
}

export type WalletLedgerListResponse = {
  items: WalletLedgerEntryPublic[]
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

async function fetchWalletMe(): Promise<WalletSummaryResponse> {
  const res = await apiFetch('/api/v1/wallet/me')
  if (!res.ok) await parseError(res)
  return res.json()
}

async function fetchWalletLedger(userId: number | null): Promise<WalletLedgerListResponse> {
  const p = new URLSearchParams({ limit: '50', offset: '0' })
  if (userId != null) p.set('user_id', String(userId))
  const res = await apiFetch(`/api/v1/wallet/ledger?${p}`)
  if (!res.ok) await parseError(res)
  return res.json()
}

export async function postWalletAdjustment(body: {
  user_id: number
  amount_cents: number
  idempotency_key: string
  note?: string
}): Promise<WalletLedgerEntryPublic> {
  const res = await apiFetch('/api/v1/wallet/adjustments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

export function useWalletMeQuery(enabled = true) {
  return useQuery({
    queryKey: ['wallet', 'me'],
    queryFn: fetchWalletMe,
    enabled,
  })
}

export function useWalletLedgerQuery(userId: number | null, enabled = true) {
  return useQuery({
    queryKey: ['wallet', 'ledger', userId],
    queryFn: () => fetchWalletLedger(userId),
    enabled,
  })
}

function invalidateWallet(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['wallet'] })
}

export function useWalletAdjustmentMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: postWalletAdjustment,
    onSuccess: () => invalidateWallet(qc),
  })
}
