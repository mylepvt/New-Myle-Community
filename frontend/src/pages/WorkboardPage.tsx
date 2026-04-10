import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { LEAD_STATUS_OPTIONS, type LeadStatus } from '@/hooks/use-leads-query'
import { useWorkboardQuery } from '@/hooks/use-workboard-query'

type Props = {
  title: string
}

function columnTitle(status: string): string {
  return LEAD_STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status
}

export function WorkboardPage({ title }: Props) {
  const { data, isPending, isError, error, refetch } = useWorkboardQuery(true)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
        <p className="max-w-md text-xs text-muted-foreground">
          Scoped like My Leads: newest cards per column (cap from API). Change status on the{' '}
          <Link to="/dashboard/work/leads" className="text-primary underline-offset-2 hover:underline">
            Leads
          </Link>{' '}
          page.
        </p>
      </div>

      {isPending ? (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-64 shrink-0 rounded-lg" />
          ))}
        </div>
      ) : null}

      {isError ? (
        <div className="text-sm text-destructive" role="alert">
          {error instanceof Error ? error.message : 'Could not load workboard'}{' '}
          <Button type="button" variant="ghost" size="sm" className="h-auto p-0 align-baseline" onClick={() => void refetch()}>
            Retry
          </Button>
        </div>
      ) : null}

      {data ? (
        <>
          <p className="text-xs text-muted-foreground">
            Loaded up to {data.max_rows_fetched} recent leads for bucketing.
          </p>
          <div className="flex gap-3 overflow-x-auto pb-4">
            {data.columns.map((col) => (
              <section
                key={col.status}
                className="flex w-64 shrink-0 flex-col rounded-lg border border-white/10 bg-card/40"
              >
                <header className="border-b border-white/10 px-3 py-2">
                  <h2 className="text-sm font-medium text-foreground">{columnTitle(col.status)}</h2>
                  <p className="text-xs text-muted-foreground">
                    {col.items.length} shown · {col.total} total
                  </p>
                </header>
                <ul className="flex max-h-[min(28rem,60vh)] flex-col gap-2 overflow-y-auto p-2">
                  {col.items.length === 0 ? (
                    <li className="rounded-md border border-dashed border-white/10 px-2 py-6 text-center text-xs text-muted-foreground">
                      No leads
                    </li>
                  ) : (
                    col.items.map((l) => (
                      <li
                        key={l.id}
                        className="rounded-md border border-white/5 bg-background/40 px-2 py-2 text-xs"
                      >
                        <span className="font-medium text-foreground">{l.name}</span>
                        <span className="mt-0.5 block text-muted-foreground">
                          #{l.id} · {l.status as LeadStatus}
                        </span>
                      </li>
                    ))
                  )}
                </ul>
              </section>
            ))}
          </div>
        </>
      ) : null}
    </div>
  )
}
