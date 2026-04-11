import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useReviewRechargeRequestMutation,
  useWalletRechargeRequestsQuery,
  type WalletRecharge,
} from '@/hooks/use-wallet-recharge-query'

type Props = {
  title: string
}

type FilterTab = 'all' | 'pending' | 'approved' | 'rejected'

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

const FILTER_TABS: { value: FilterTab; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

function RechargeRow({
  item,
  reviewMut,
}: {
  item: WalletRecharge
  reviewMut: ReturnType<typeof useReviewRechargeRequestMutation>
}) {
  const [showRejectNote, setShowRejectNote] = useState(false)
  const [rejectNote, setRejectNote] = useState('')
  const [rowError, setRowError] = useState('')

  async function handleApprove() {
    setRowError('')
    try {
      await reviewMut.mutateAsync({ id: item.id, body: { status: 'approved' } })
    } catch (e) {
      setRowError(e instanceof Error ? e.message : 'Action failed')
    }
  }

  async function handleReject() {
    setRowError('')
    try {
      await reviewMut.mutateAsync({
        id: item.id,
        body: { status: 'rejected', admin_note: rejectNote.trim() || undefined },
      })
      setShowRejectNote(false)
      setRejectNote('')
    } catch (e) {
      setRowError(e instanceof Error ? e.message : 'Action failed')
    }
  }

  return (
    <li className="surface-elevated p-4 space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-0.5 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">
              ₹{(item.amount_cents / 100).toFixed(2)}
            </span>
            <RechargeStatusBadge status={item.status} />
            <span className="text-xs text-muted-foreground">User #{item.user_id}</span>
          </div>
          {item.utr_number ? (
            <p className="text-xs text-muted-foreground">UTR: {item.utr_number}</p>
          ) : null}
          {item.proof_url ? (
            <a
              href={item.proof_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary underline-offset-2 hover:underline"
            >
              View proof
            </a>
          ) : null}
          <p className="text-xs text-muted-foreground">
            Submitted {new Date(item.created_at).toLocaleString()}
          </p>
          {item.reviewed_at ? (
            <p className="text-xs text-muted-foreground">
              Reviewed {new Date(item.reviewed_at).toLocaleString()}
              {item.reviewed_by_user_id ? ` by user #${item.reviewed_by_user_id}` : ''}
            </p>
          ) : null}
          {item.admin_note ? (
            <p className="text-xs text-muted-foreground">Note: {item.admin_note}</p>
          ) : null}
        </div>

        {item.status === 'pending' ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              disabled={reviewMut.isPending}
              onClick={() => void handleApprove()}
            >
              Approve
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={reviewMut.isPending}
              onClick={() => setShowRejectNote((v) => !v)}
              className="text-destructive hover:text-destructive"
            >
              Reject
            </Button>
          </div>
        ) : null}
      </div>

      {showRejectNote ? (
        <div className="surface-inset space-y-2 p-3">
          <label
            htmlFor={`reject-note-${item.id}`}
            className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            Rejection note (optional)
          </label>
          <input
            id={`reject-note-${item.id}`}
            type="text"
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
            placeholder="Reason…"
            className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={reviewMut.isPending}
              className="text-destructive hover:text-destructive"
              onClick={() => void handleReject()}
            >
              {reviewMut.isPending ? 'Rejecting…' : 'Confirm reject'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setShowRejectNote(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {rowError ? <p className="text-xs text-destructive">{rowError}</p> : null}
    </li>
  )
}

export function WalletRechargeAdminPage({ title }: Props) {
  const requestsQuery = useWalletRechargeRequestsQuery()
  const reviewMut = useReviewRechargeRequestMutation()
  const [activeTab, setActiveTab] = useState<FilterTab>('all')

  const allItems = requestsQuery.data?.items ?? []
  const filtered =
    activeTab === 'all' ? allItems : allItems.filter((r) => r.status === activeTab)

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => void requestsQuery.refetch()}
          disabled={requestsQuery.isFetching}
        >
          {requestsQuery.isFetching ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1">
        {FILTER_TABS.map((tab) => {
          const count =
            tab.value === 'all'
              ? allItems.length
              : allItems.filter((r) => r.status === tab.value).length
          const isActive = activeTab === tab.value
          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-white/[0.05] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground'
              }`}
            >
              {tab.label}
              {count > 0 ? (
                <span className="ml-1.5 tabular-nums opacity-75">({count})</span>
              ) : null}
            </button>
          )
        })}
      </div>

      {requestsQuery.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : null}

      {requestsQuery.isError ? (
        <p className="text-sm text-destructive">
          {requestsQuery.error instanceof Error
            ? requestsQuery.error.message
            : 'Could not load requests'}
        </p>
      ) : null}

      {requestsQuery.data && filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {activeTab === 'all'
            ? 'No recharge requests.'
            : `No ${activeTab} requests.`}
        </p>
      ) : null}

      {filtered.length > 0 ? (
        <ul className="space-y-3">
          {filtered.map((item) => (
            <RechargeRow key={item.id} item={item} reviewMut={reviewMut} />
          ))}
        </ul>
      ) : null}
    </div>
  )
}
