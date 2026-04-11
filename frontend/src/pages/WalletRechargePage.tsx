import { type FormEvent, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useCreateRechargeRequestMutation,
  useWalletRechargeRequestsQuery,
} from '@/hooks/use-wallet-recharge-query'

type Props = {
  title: string
}

function RechargeStatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    pending: 'bg-amber-400/15 text-amber-400',
    approved: 'bg-[hsl(142_71%_48%)]/15 text-[hsl(142_71%_48%)]',
    rejected: 'bg-destructive/15 text-destructive',
  }
  const c = cls[status] ?? 'bg-muted/30 text-muted-foreground'
  const labels: Record<string, string> = {
    pending: 'Pending',
    approved: 'Approved',
    rejected: 'Rejected',
  }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${c}`}>
      {labels[status] ?? status}
    </span>
  )
}

export function WalletRechargePage({ title }: Props) {
  const requestsQuery = useWalletRechargeRequestsQuery()
  const createMut = useCreateRechargeRequestMutation()

  const [amount, setAmount] = useState('')
  const [utr, setUtr] = useState('')
  const [proofUrl, setProofUrl] = useState('')
  const [formError, setFormError] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError('')
    const amountRupees = parseFloat(amount)
    if (!Number.isFinite(amountRupees) || amountRupees <= 0) {
      setFormError('Enter a valid amount')
      return
    }
    const amount_cents = Math.round(amountRupees * 100)
    const idempotency_key =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `recharge-${Date.now()}-${Math.random().toString(36).slice(2)}`
    try {
      await createMut.mutateAsync({
        amount_cents,
        utr_number: utr.trim() || undefined,
        proof_url: proofUrl.trim() || undefined,
        idempotency_key,
      })
      setAmount('')
      setUtr('')
      setProofUrl('')
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Request failed')
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        Submit your wallet recharge request below. An admin will review and credit your balance.
      </p>

      {/* Request form */}
      <form onSubmit={(e) => void handleSubmit(e)} className="surface-elevated space-y-4 p-4">
        <p className="text-sm font-medium text-foreground">New recharge request</p>

        <div>
          <label
            htmlFor="recharge-amount"
            className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            Amount (₹)
          </label>
          <input
            id="recharge-amount"
            type="number"
            min="1"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            placeholder="e.g. 500"
            className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
        </div>

        <div>
          <label
            htmlFor="recharge-utr"
            className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            UTR number (optional)
          </label>
          <input
            id="recharge-utr"
            type="text"
            value={utr}
            onChange={(e) => setUtr(e.target.value)}
            placeholder="Bank reference number"
            className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
        </div>

        <div>
          <label
            htmlFor="recharge-proof"
            className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            Proof URL (optional)
          </label>
          <input
            id="recharge-proof"
            type="url"
            value={proofUrl}
            onChange={(e) => setProofUrl(e.target.value)}
            placeholder="https://…"
            className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
        </div>

        {formError ? (
          <p className="text-xs text-destructive">{formError}</p>
        ) : null}

        {createMut.isError && !formError ? (
          <p className="text-xs text-destructive">
            {createMut.error instanceof Error ? createMut.error.message : 'Request failed'}
          </p>
        ) : null}

        {createMut.isSuccess ? (
          <p className="text-xs text-[hsl(142_71%_48%)]">
            Request submitted! An admin will review it shortly.
          </p>
        ) : null}

        <Button type="submit" disabled={createMut.isPending || !amount}>
          {createMut.isPending ? 'Submitting…' : 'Submit request'}
        </Button>
      </form>

      {/* My requests */}
      <div className="surface-elevated p-4 space-y-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          My requests
        </p>

        {requestsQuery.isPending ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : null}

        {requestsQuery.isError ? (
          <p className="text-xs text-destructive">
            {requestsQuery.error instanceof Error
              ? requestsQuery.error.message
              : 'Could not load requests'}
          </p>
        ) : null}

        {requestsQuery.data && requestsQuery.data.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recharge requests yet.</p>
        ) : null}

        {requestsQuery.data && requestsQuery.data.items.length > 0 ? (
          <ul className="space-y-2">
            {requestsQuery.data.items.map((r) => (
              <li key={r.id} className="surface-inset px-3 py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-medium text-foreground">
                      ₹{(r.amount_cents / 100).toFixed(2)}
                    </span>
                    {r.utr_number ? (
                      <span className="ml-2 text-xs text-muted-foreground">UTR: {r.utr_number}</span>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <RechargeStatusBadge status={r.status} />
                    <span className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                {r.admin_note ? (
                  <p className="mt-1 text-xs text-muted-foreground">Note: {r.admin_note}</p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  )
}
