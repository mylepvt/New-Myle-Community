import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useLeadsQuery, usePatchLeadMutation, type LeadListFilters } from '@/hooks/use-leads-query'

type Props = {
  title: string
}

const emptyFilters: LeadListFilters = { q: '', status: '' }

export function RecycleBinWorkPage({ title }: Props) {
  const { data, isPending, isError, error, refetch } = useLeadsQuery(true, emptyFilters, 'recycle')
  const patchMut = usePatchLeadMutation()

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
        <Link
          to="/dashboard/work/leads"
          className="text-sm text-primary underline-offset-2 hover:underline"
        >
          ← Active leads
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">
        Soft-deleted leads (admin only). Restoring clears trash and returns the lead to the normal list if it was not
        in the pool.
      </p>

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : null}
      {isError ? (
        <div className="text-sm text-destructive" role="alert">
          <span>{error instanceof Error ? error.message : 'Could not load recycle bin'} </span>
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}
      {data ? (
        <div className="rounded-lg border border-white/10 bg-card/40 p-4 text-sm text-muted-foreground">
          <p className="mb-3 font-medium text-foreground">Deleted: {data.total}</p>
          {data.items.length === 0 ? (
            <p>Recycle bin is empty.</p>
          ) : (
            <ul className="space-y-2">
              {data.items.map((l) => (
                <li
                  key={l.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-white/5 bg-background/30 px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <span className="font-medium text-foreground">{l.name}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      #{l.id} · deleted{' '}
                      {l.deleted_at ? new Date(l.deleted_at).toLocaleString() : '—'}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={patchMut.isPending}
                    onClick={() => void patchMut.mutateAsync({ id: l.id, body: { restored: true } })}
                  >
                    Restore
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {patchMut.isError ? (
            <p className="mt-2 text-xs text-destructive">
              {patchMut.error instanceof Error ? patchMut.error.message : 'Restore failed'}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
