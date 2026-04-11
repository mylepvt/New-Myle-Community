import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useApiMetaQuery } from '@/hooks/use-api-meta-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { useHelloQuery } from '@/hooks/use-hello-query'
import { apiBase } from '@/lib/api'
import { authLogout } from '@/lib/auth-api'
import { useAuthStore } from '@/stores/auth-store'

export function HomePage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { data, error, isPending } = useHelloQuery()
  const { data: meta } = useApiMetaQuery()
  const { data: me, isPending: mePending } = useAuthMeQuery()
  const logout = useAuthStore((s) => s.logout)
  const sessionKnown = !mePending || me !== undefined
  const sessionActive = Boolean(me?.authenticated)

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6 p-6">
      <div>
        <h1 className="bg-gradient-to-br from-foreground via-foreground to-primary/75 bg-clip-text text-3xl font-semibold tracking-tight text-transparent">
          Myle vl2
        </h1>
      </div>
      <div className="surface-elevated p-5 text-card-foreground">
        <p className="text-sm font-medium">API</p>
        <div className="mt-3 min-h-[1.5rem] text-sm" aria-live="polite">
          {isPending && (
            <div className="space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          )}
          {error && (
            <p className="text-destructive" role="alert">
              {(error as Error).message}
            </p>
          )}
          {data && <p>{data.message}</p>}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          <code className="rounded-md border border-white/10 bg-muted/50 px-2 py-1 font-mono text-[0.7rem] text-muted-foreground">
            {apiBase}/api/v1/hello
          </code>
        </p>
        {meta ? (
          <p className="mt-2 text-xs text-muted-foreground">
            {meta.name} · v{meta.api_version}
          </p>
        ) : null}
        {me?.authenticated ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Session: {me.role ?? '—'}
          </p>
        ) : null}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <Button asChild>
          <Link to="/dashboard">Dashboard</Link>
        </Button>
        {!sessionKnown ? (
          <Button variant="secondary" disabled>
            Checking session…
          </Button>
        ) : !sessionActive ? (
          <Button variant="secondary" asChild>
            <Link to="/login">Sign in</Link>
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            onClick={async () => {
              try {
                await authLogout()
              } catch {
                /* still clear local session */
              }
              logout()
              await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
              navigate('/login', { replace: true })
            }}
          >
            Sign out
          </Button>
        )}
      </div>
    </div>
  )
}
