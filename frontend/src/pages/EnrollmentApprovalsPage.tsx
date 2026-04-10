import { Skeleton } from '@/components/ui/skeleton'
import { useEnrollmentRequestsQuery } from '@/hooks/use-team-query'

type Props = { title: string }

export function EnrollmentApprovalsPage({ title }: Props) {
  const { data, isPending, isError, error, refetch } = useEnrollmentRequestsQuery()

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        Paid enrollment approvals (e.g. INR 196 tier) will appear here once the workflow is persisted. The API already returns an
        empty list with stable pagination fields.
      </p>

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
        <div className="rounded-lg border border-white/10 bg-card/40 p-4 text-sm text-muted-foreground">
          <p className="mb-2 font-medium text-foreground">Pending: {data.total}</p>
          {data.total === 0 ? (
            <p>No enrollment requests in the queue.</p>
          ) : (
            <ul className="space-y-2">
              {data.items.map((row, i) => (
                <li key={i} className="text-xs">
                  {JSON.stringify(row)}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}
