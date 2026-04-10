import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  LEAD_STATUS_OPTIONS,
  useClaimLeadMutation,
  usePatchLeadMutation,
} from '@/hooks/use-leads-query'
import { useLeadPoolQuery } from '@/hooks/use-lead-pool-query'
import { useRoleStore } from '@/stores/role-store'

type Props = {
  title: string
}

function statusLabel(value: string): string {
  return LEAD_STATUS_OPTIONS.find((o) => o.value === value)?.label ?? value
}

export function LeadPoolWorkPage({ title }: Props) {
  const role = useRoleStore((s) => s.role)
  const { data, isPending, isError, error, refetch } = useLeadPoolQuery()
  const claimMut = useClaimLeadMutation()
  const patchMut = usePatchLeadMutation()

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
        <Link
          to="/dashboard/work/leads"
          className="text-sm text-primary underline-offset-2 hover:underline"
        >
          ← My / all leads
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">
        Leads an admin has released into the shared pool appear here. Claim one to assign it to yourself — it then
        shows on your main list and workboard.
      </p>

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : null}
      {isError ? (
        <div className="text-sm text-destructive" role="alert">
          <span>{error instanceof Error ? error.message : 'Could not load pool'} </span>
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
          <p className="mb-3 font-medium text-foreground">In pool: {data.total}</p>
          {data.items.length === 0 ? (
            <p>No pooled leads right now.</p>
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
                      #{l.id} · {statusLabel(l.status)} · added {new Date(l.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {role === 'admin' ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={patchMut.isPending}
                        title="Return to main lead list without assigning"
                        onClick={() => void patchMut.mutateAsync({ id: l.id, body: { in_pool: false } })}
                      >
                        Out of pool
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      disabled={claimMut.isPending}
                      onClick={() => void claimMut.mutateAsync(l.id)}
                    >
                      {claimMut.isPending ? 'Claiming…' : 'Claim'}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {claimMut.isError ? (
            <p className="mt-2 text-xs text-destructive">
              {claimMut.error instanceof Error ? claimMut.error.message : 'Claim failed'}
            </p>
          ) : null}
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
