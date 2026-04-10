import { type FormEvent, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useShellStubQuery } from '@/hooks/use-shell-stub-query'
import { useTeamMembersQuery } from '@/hooks/use-team-query'
import { useWalletAdjustmentMutation } from '@/hooks/use-wallet-query'

type Props = { title: string }

export function FinanceRechargesPage({ title }: Props) {
  const stub = useShellStubQuery('/api/v1/finance/recharges')
  const members = useTeamMembersQuery(true)
  const mut = useWalletAdjustmentMutation()
  const [userId, setUserId] = useState('')
  const [amountCents, setAmountCents] = useState('')
  const [note, setNote] = useState('')

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const uid = Number(userId)
    const cents = Number(amountCents)
    if (!Number.isFinite(uid) || uid < 1 || !Number.isFinite(cents)) return
    const idempotency_key =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `recharge-${Date.now()}-${Math.random().toString(36).slice(2)}`
    try {
      await mut.mutateAsync({
        user_id: uid,
        amount_cents: Math.trunc(cents),
        idempotency_key,
        note: note.trim() || undefined,
      })
      setAmountCents('')
      setNote('')
    } catch {
      /* surfaced below */
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>

      {stub.isPending ? <Skeleton className="h-12 w-full" /> : null}
      {stub.data?.note ? (
        <p className="rounded-lg border border-white/10 bg-card/40 p-3 text-sm text-muted-foreground">
          {stub.data.note}
        </p>
      ) : null}

      <form onSubmit={(e) => void onSubmit(e)} className="space-y-4 rounded-lg border border-white/10 bg-card/30 p-4">
        <p className="text-sm font-medium text-foreground">Credit / debit user wallet</p>
        <p className="text-xs text-muted-foreground">
          Amount in <strong>minor units (paise / cents)</strong> (e.g. 10000 = INR 100.00 credit). Negative values debit.
        </p>
        {members.isPending ? <Skeleton className="h-10 w-full" /> : null}
        {members.data ? (
          <div>
            <label htmlFor="recharge-user" className="mb-1 block text-xs text-muted-foreground">
              User
            </label>
            <select
              id="recharge-user"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              required
              className="w-full rounded-md border border-white/10 bg-card/80 px-3 py-2 text-sm text-foreground"
            >
              <option value="">Select…</option>
              {members.data.items.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.email} ({m.role})
                </option>
              ))}
            </select>
          </div>
        ) : null}
        {members.isError ? (
          <p className="text-xs text-destructive">Could not load members (admin only).</p>
        ) : null}
        <div>
          <label htmlFor="recharge-cents" className="mb-1 block text-xs text-muted-foreground">
            Amount (cents)
          </label>
          <input
            id="recharge-cents"
            type="number"
            value={amountCents}
            onChange={(e) => setAmountCents(e.target.value)}
            required
            className="w-full rounded-md border border-white/10 bg-card/80 px-3 py-2 text-sm text-foreground"
          />
        </div>
        <div>
          <label htmlFor="recharge-note" className="mb-1 block text-xs text-muted-foreground">
            Note (optional)
          </label>
          <input
            id="recharge-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="w-full rounded-md border border-white/10 bg-card/80 px-3 py-2 text-sm text-foreground"
          />
        </div>
        <Button type="submit" disabled={mut.isPending || !userId}>
          {mut.isPending ? 'Applying…' : 'Apply adjustment'}
        </Button>
        {mut.isError ? (
          <p className="text-xs text-destructive">
            {mut.error instanceof Error ? mut.error.message : 'Request failed'}
          </p>
        ) : null}
        {mut.isSuccess ? <p className="text-xs text-emerald-500">Ledger line recorded.</p> : null}
      </form>
    </div>
  )
}
