import { Link } from 'react-router-dom'

import { Skeleton } from '@/components/ui/skeleton'
import {
  LEAD_STATUS_OPTIONS,
  type LeadStatus,
  usePatchLeadMutation,
} from '@/hooks/use-leads-query'
import { useRetargetQuery } from '@/hooks/use-retarget-query'

type Props = {
  title: string
}

function statusLabel(v: string): string {
  return LEAD_STATUS_OPTIONS.find((o) => o.value === v)?.label ?? v
}

export function RetargetWorkPage({ title }: Props) {
  const { data, isPending, isError, error, refetch } = useRetargetQuery()
  const patchMut = usePatchLeadMutation()

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        Shows active leads in <strong>Lost</strong> or <strong>Contacted</strong> — good candidates to re-engage.
        Change status from{' '}
        <Link to="/dashboard/work/leads" className="text-primary underline-offset-2 hover:underline">
          My Leads
        </Link>{' '}
        or here.
      </p>

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : null}
      {isError ? (
        <p className="text-sm text-destructive" role="alert">
          {error instanceof Error ? error.message : 'Failed to load'}{' '}
          <button type="button" className="underline" onClick={() => void refetch()}>
            Retry
          </button>
        </p>
      ) : null}

      {data ? (
        <div className="surface-elevated p-4 text-sm">
          <p className="mb-3 font-medium text-foreground">Total: {data.total}</p>
          {data.items.length === 0 ? (
            <p className="text-muted-foreground">No retarget candidates — move a lead to Lost or Contacted first.</p>
          ) : (
            <ul className="space-y-2">
              {data.items.map((l) => (
                <li
                  key={l.id}
                  className="surface-inset flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                >
                  <div>
                    <span className="font-medium text-foreground">{l.name}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      #{l.id} · {statusLabel(l.status)}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      aria-label={`Status for ${l.name}`}
                      value={l.status}
                      disabled={patchMut.isPending}
                      onChange={(e) => {
                        void patchMut.mutateAsync({
                          id: l.id,
                          body: { status: e.target.value as LeadStatus },
                        })
                      }}
                      className="rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-2 py-1.5 text-xs text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
                    >
                      {LEAD_STATUS_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {patchMut.isError ? (
            <p className="mt-2 text-xs text-destructive">
              {patchMut.error instanceof Error ? patchMut.error.message : 'Update failed'}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
