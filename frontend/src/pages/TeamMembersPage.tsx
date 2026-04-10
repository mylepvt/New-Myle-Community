import { Skeleton } from '@/components/ui/skeleton'
import { useTeamMembersQuery } from '@/hooks/use-team-query'

type Props = { title: string }

export function TeamMembersPage({ title }: Props) {
  const { data, isPending, isError, error, refetch } = useTeamMembersQuery()

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        All accounts in this environment (from the users table). Passwords are never exposed via this API.
      </p>

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : null}
      {isError ? (
        <div className="text-sm text-destructive" role="alert">
          <span>{error instanceof Error ? error.message : 'Could not load members'} </span>
          <button type="button" className="underline underline-offset-2" onClick={() => void refetch()}>
            Retry
          </button>
        </div>
      ) : null}
      {data ? (
        <div className="rounded-lg border border-white/10 bg-card/40 p-4 text-sm">
          <p className="mb-3 font-medium text-foreground">Total: {data.total}</p>
          <ul className="space-y-2">
            {data.items.map((m) => (
              <li
                key={m.id}
                className="rounded-md border border-white/5 bg-background/30 px-3 py-2 text-muted-foreground"
              >
                <span className="font-medium text-foreground">{m.email}</span>
                <span className="mt-0.5 block text-xs">
                  {m.role} · joined {new Date(m.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
