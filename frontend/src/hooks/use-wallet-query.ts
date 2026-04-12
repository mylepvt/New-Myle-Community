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

// Enhanced wallet types
export type WalletTransaction = {
  id: number
  amount_cents: number
  amount_rupees: number
  currency: string
  note: string
  created_at: string
}

export type WalletSummaryEnhanced = {
  balance_cents: number
  currency: string
  balance_rupees: number
  recent_transactions: WalletTransaction[]
  pending_recharges: number
  monthly_spending_cents: number
  monthly_spending_rupees: number
}

export type WalletOverview = {
  total_balance_cents: number
  total_balance_rupees: number
  user_count: number
  pending_recharge_requests: number
  top_balances: Array<{
    user_id: number
    balance_cents: number
    balance_rupees: number
  }>
  recent_activity: Array<{
    id: number
    user_id: number
    amount_cents: number
    amount_rupees: number
    note: string
    created_at: string
  }>
}

export type LeadClaimRequest = {
  lead_id: number
  lead_price_cents: number
}

export type LeadClaimResponse = {
  success: boolean
  message: string
  lead_id: number
  amount_deducted_cents: number
  new_balance_cents: number
  currency: string
}

export type WalletAdjustmentRequest = {
  target_user_id: number
  amount_cents: number
  note: string
}

export type WalletAdjustmentResponse = {
  success: boolean
  message: string
  target_user_id: number
  amount_cents: number
  new_balance_cents: number
  currency: string
}

// Enhanced wallet API functions
async function fetchWalletSummaryEnhanced(): Promise<WalletSummaryEnhanced> {
  const res = await apiFetch('/api/v1/wallet/enhanced/summary')
  if (!res.ok) await parseError(res)
  return res.json()
}

async function fetchWalletOverview(): Promise<WalletOverview> {
  const res = await apiFetch('/api/v1/wallet/enhanced/overview')
  if (!res.ok) await parseError(res)
  return res.json()
}

async function claimLeadWithWallet(request: LeadClaimRequest): Promise<LeadClaimResponse> {
  const res = await apiFetch('/api/v1/wallet/enhanced/lead-claim', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

async function createManualAdjustment(request: WalletAdjustmentRequest): Promise<WalletAdjustmentResponse> {
  const res = await apiFetch('/api/v1/wallet/enhanced/manual-adjustment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

async function validatePurchase(amountCents: number): Promise<{
  can_afford: boolean
  message: string
  current_balance_cents: number
  current_balance_rupees: number
  required_amount_cents: number
  required_amount_rupees: number
}> {
  const res = await apiFetch('/api/v1/wallet/enhanced/validate-purchase', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_cents: amountCents }),
  })
  if (!res.ok) await parseError(res)
  return res.json()
}

// Enhanced wallet hooks
export function useWalletSummaryEnhancedQuery() {
  return useQuery({
    queryKey: ['wallet', 'enhanced', 'summary'],
    queryFn: fetchWalletSummaryEnhanced,
    staleTime: 30_000,
  })
}

export function useWalletOverviewQuery() {
  return useQuery({
    queryKey: ['wallet', 'enhanced', 'overview'],
    queryFn: fetchWalletOverview,
    staleTime: 60_000,
  })
}

export function useLeadClaimMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: claimLeadWithWallet,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wallet'] })
      qc.invalidateQueries({ queryKey: ['pipeline'] })
    },
  })
}

export function useManualAdjustmentMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createManualAdjustment,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wallet'] })
    },
  })
}

export function usePurchaseValidationQuery(amountCents: number) {
  return useQuery({
    queryKey: ['wallet', 'validate-purchase', amountCents],
    queryFn: () => validatePurchase(amountCents),
    staleTime: 30_000,
    enabled: amountCents > 0,
  })
}
