import { Skeleton } from '@/components/ui/skeleton'
import {
  useAnalyticsSurfaceQuery,
  type AnalyticsSurface,
} from '@/hooks/use-analytics-surface-query'

type Props = {
  title: string
  surface: AnalyticsSurface
}

export function AnalyticsSurfacePage({ title, surface }: Props) {
  const { data, isPending, isError, error, refetch } = useAnalyticsSurfaceQuery(surface)

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
        </div>
      ) : null}
      {isError ? (
        <div className="text-sm text-destructive" role="alert">
          <span>{error instanceof Error ? error.message : 'Could not load'} </span>
          <button type="button" className="underline underline-offset-2" onClick={() => void refetch()}>
            Retry
          </button>
        </div>
      ) : null}
      {data ? (
        <div className="space-y-3 rounded-lg border border-white/10 bg-card/40 p-4 text-sm text-muted-foreground">
          {data.note ? <p className="text-foreground/90">{data.note}</p> : null}
          <p>
            Rows: <span className="font-medium text-foreground">{data.total}</span>
            {data.items.length > 0 ? (
              <ul className="mt-2 space-y-1 text-xs">
                {data.items.map((row, i) => (
                  <li key={i}>{JSON.stringify(row)}</li>
                ))}
              </ul>
            ) : null}
          </p>
        </div>
      ) : null}
    </div>
  )
}
