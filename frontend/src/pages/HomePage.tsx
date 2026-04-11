import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Shield } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useApiMetaQuery } from '@/hooks/use-api-meta-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { useHelloQuery } from '@/hooks/use-hello-query'
import { apiBase } from '@/lib/api'
import { authLogout } from '@/lib/auth-api'
import { t } from '@/lib/i18n'
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
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(2rem,env(safe-area-inset-top))]">
      <header className="flex flex-1 flex-col justify-center gap-10">
        <div className="space-y-3 text-center">
          <p className="text-sm font-semibold text-primary">{t('appTitle')}</p>
          <h1 className="bg-gradient-to-br from-foreground via-foreground to-primary/80 bg-clip-text text-3xl font-semibold tracking-tight text-transparent sm:text-4xl">
            Your sales workspace
          </h1>
          <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
            {t('appTagline')}
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button asChild size="lg" className="gap-2">
            <Link to="/dashboard">
              Open app
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
          {!sessionKnown ? (
            <Button variant="secondary" size="lg" disabled>
              Checking session…
            </Button>
          ) : !sessionActive ? (
            <Button variant="secondary" size="lg" asChild>
              <Link to="/login">Sign in</Link>
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="lg"
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

        <Card className="shadow-sm">
          <CardContent className="flex items-start gap-3">
            <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <Shield className="size-4" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <CardTitle className="text-ds-body font-medium leading-snug">
                Service status
              </CardTitle>
              <div className="mt-2 min-h-[1.25rem] text-ds-body" aria-live="polite">
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
                {data && (
                  <p className="text-muted-foreground">{data.message}</p>
                )}
              </div>
              <p className="mt-3 text-ds-caption text-muted-foreground">
                <code className="rounded-md border border-border bg-muted/50 px-2 py-1 font-mono text-ds-caption">
                  {apiBase}/api/v1/hello
                </code>
              </p>
              {meta ? (
                <p className="mt-2 text-ds-caption text-muted-foreground">
                  {meta.name} · API v{meta.api_version}
                </p>
              ) : null}
              {me?.authenticated ? (
                <p className="mt-2 text-ds-caption text-muted-foreground">
                  Signed in as {me.role ?? 'member'}
                </p>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </header>

      <footer className="mt-auto border-t border-white/[0.06] py-6 text-center text-[0.65rem] text-muted-foreground/80">
        © {new Date().getFullYear()} {t('appTitle')} · Internal use
      </footer>
    </div>
  )
}
