import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { 
  Wallet, 
  TrendingUp, 
  TrendingDown, 
  CreditCard, 
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Settings
} from 'lucide-react'
import { 
  useWalletLedgerQuery, 
  useWalletMeQuery,
  useWalletSummaryEnhancedQuery,
  useWalletOverviewQuery,
  useLeadClaimMutation,
  useManualAdjustmentMutation
} from '@/hooks/use-wallet-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'

type Props = { title: string }

function formatMoney(cents: number, currency: string) {
  const major = cents / 100
  return `${currency} ${major.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function WalletPage({ title }: Props) {
  const me = useWalletMeQuery()
  const enhanced = useWalletSummaryEnhancedQuery()
  const overview = useWalletOverviewQuery()
  const ledger = useWalletLedgerQuery(null)
  const { data: authData } = useAuthMeQuery()
  const claimMutation = useLeadClaimMutation()
  const adjustmentMutation = useManualAdjustmentMutation()
  const [showAdminPanel, setShowAdminPanel] = useState(false)

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        Balance is the sum of all ledger lines (append-only). Credits and debits are applied by admins via Finance →
        Recharges.
      </p>

      {me.isPending ? <Skeleton className="h-16 w-full" /> : null}
      {me.isError ? (
        <p className="text-sm text-destructive">{me.error instanceof Error ? me.error.message : 'Error'}</p>
      ) : null}
      {me.data ? (
        <div className="surface-elevated p-4">
          <p className="text-xs font-medium text-muted-foreground">Balance</p>
          <p className="text-2xl font-semibold tracking-tight text-foreground">
            {formatMoney(me.data.balance_cents, me.data.currency)}
          </p>
        </div>
      ) : null}

      <div>
        <h2 className="mb-2 text-sm font-medium text-foreground">Recent activity</h2>
        {me.isPending ? <Skeleton className="h-24 w-full" /> : null}
        {me.data && me.data.recent_entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No ledger lines yet.</p>
        ) : null}
        {me.data && me.data.recent_entries.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {me.data.recent_entries.map((e) => (
              <li
                key={e.id}
                className="surface-inset px-3 py-2 text-muted-foreground"
              >
                <span className={e.amount_cents >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                  {e.amount_cents >= 0 ? '+' : ''}
                  {(e.amount_cents / 100).toFixed(2)} {e.currency}
                </span>
                {e.note ? <span className="ml-2 text-xs">{e.note}</span> : null}
                <span className="mt-1 block text-xs">{new Date(e.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-medium text-foreground">Ledger (paged)</h2>
        {ledger.isPending ? <Skeleton className="h-20 w-full" /> : null}
        {ledger.isError ? (
          <p className="text-sm text-destructive">{ledger.error instanceof Error ? ledger.error.message : 'Error'}</p>
        ) : null}
        {ledger.data ? (
          <p className="text-xs text-muted-foreground">
            Total lines: {ledger.data.total} (showing {ledger.data.items.length})
          </p>
        ) : null}
        {ledger.data && ledger.data.items.length > 0 ? (
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
            {ledger.data.items.map((e) => (
              <li key={e.id}>
                #{e.id} · {e.amount_cents >= 0 ? '+' : ''}
                {(e.amount_cents / 100).toFixed(2)} · {new Date(e.created_at).toLocaleString()}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  )
}
