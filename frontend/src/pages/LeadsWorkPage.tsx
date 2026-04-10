import { useLeadsQuery } from '@/hooks/use-leads-query'
import { Skeleton } from '@/components/ui/skeleton'

type Props = {
  title: string
}

export function LeadsWorkPage({ title }: Props) {
  const { data, isPending, isError, error, refetch } = useLeadsQuery(true)

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : null}
      {isError ? (
        <div className="text-sm text-destructive" role="alert">
          <span>
            {error instanceof Error ? error.message : 'Could not load leads'}{' '}
          </span>
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
          <p className="mb-2 font-medium text-foreground">Total: {data.total}</p>
          {data.items.length === 0 ? (
            <p>No leads yet — API stub returns an empty list until the DB is wired.</p>
          ) : (
            <ul className="list-inside list-disc space-y-1">
              {data.items.map((l) => (
                <li key={l.id}>
                  <span className="text-foreground">{l.name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}
