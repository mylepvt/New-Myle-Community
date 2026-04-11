import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { authDevLogin, authPasswordLogin, DEV_SEED_PASSWORD } from '@/lib/auth-api'
import { fetchAuthMe } from '@/hooks/use-auth-me-query'
import { DEFAULT_META, useMetaQuery } from '@/hooks/use-meta-query'
import { t } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'
import { useRoleStore } from '@/stores/role-store'
import { ROLES, type Role } from '@/types/role'

export function LoginPage() {
  const { data: meta } = useMetaQuery()
  const devLoginAllowed = (meta ?? DEFAULT_META).auth_dev_login_enabled === true
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const role = useRoleStore((s) => s.role)
  const setRole = useRoleStore((s) => s.setRole)
  const from =
    (location.state as { from?: string } | null)?.from ?? '/dashboard'

  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pwPending, setPwPending] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    if (meta?.auth_dev_login_enabled) {
      setEmail((e) => (e === '' ? 'dev-leader@myle.local' : e))
    }
  }, [meta?.auth_dev_login_enabled])

  async function handlePasswordLogin() {
    setError(null)
    if (!password.trim()) {
      setError(
        devLoginAllowed
          ? `Password required — dev seed: ${DEV_SEED_PASSWORD}`
          : 'Please enter your password.',
      )
      return
    }
    if (!email.trim()) {
      setError('Please enter your email address.')
      return
    }
    setPwPending(true)
    try {
      await authPasswordLogin(email.trim(), password)
      await queryClient.resetQueries({ queryKey: ['auth', 'me'] })
      let me = await queryClient.fetchQuery({
        queryKey: ['auth', 'me'],
        queryFn: fetchAuthMe,
      })
      if (!me.authenticated) {
        await new Promise((r) => setTimeout(r, 200))
        me = await queryClient.fetchQuery({
          queryKey: ['auth', 'me'],
          queryFn: fetchAuthMe,
        })
      }
      if (!me.authenticated) {
        window.location.assign(from)
        return
      }
      login()
      navigate(from, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign-in failed')
    } finally {
      setPwPending(false)
    }
  }

  async function handleContinue() {
    setError(null)
    setPending(true)
    try {
      await authDevLogin(role)
      await queryClient.resetQueries({ queryKey: ['auth', 'me'] })
      let me = await queryClient.fetchQuery({
        queryKey: ['auth', 'me'],
        queryFn: fetchAuthMe,
      })
      if (!me.authenticated) {
        await new Promise((r) => setTimeout(r, 200))
        me = await queryClient.fetchQuery({
          queryKey: ['auth', 'me'],
          queryFn: fetchAuthMe,
        })
      }
      if (!me.authenticated) {
        window.location.assign(from)
        return
      }
      login()
      navigate(from, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign-in failed')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-[max(1.25rem,env(safe-area-inset-top))]">
      <div
        className="pointer-events-none absolute inset-0 overflow-hidden"
        aria-hidden
      >
        <div className="absolute -left-24 top-[18%] h-72 w-72 rounded-full bg-primary/[0.07] blur-3xl" />
        <div className="absolute -right-20 bottom-[22%] h-64 w-64 rounded-full bg-white/[0.04] blur-3xl" />
      </div>

      <div className="relative z-[1] w-full max-w-[min(100%,24rem)]">
        <Link
          to="/"
          className="mb-5 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4 shrink-0 opacity-80" aria-hidden />
          Back to home
        </Link>

        <div
          className={cn(
            'surface-elevated space-y-6 rounded-2xl border-white/[0.14] p-8 sm:p-9',
            'shadow-[0_24px_80px_-28px_rgba(0,0,0,0.75)]',
          )}
        >
          <div className="space-y-1 text-center sm:text-left">
            <p className="text-sm font-semibold tracking-tight text-primary">
              {t('appTitle')}
            </p>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Sign in
            </h1>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {t('appTagline')}
            </p>
          </div>

          {devLoginAllowed ? (
            <div className="space-y-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-4">
              <p className="text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-amber-200/90">
                Development
              </p>
              <label className="field-label" htmlFor="login-role">
                Preview role
              </label>
              <select
                id="login-role"
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
                disabled={pending}
                className="field-input appearance-none bg-white/[0.08]"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="secondary"
                className="w-full"
                disabled={pending}
                onClick={() => void handleContinue()}
              >
                {pending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    Signing in…
                  </>
                ) : (
                  'Continue with preview role'
                )}
              </Button>
            </div>
          ) : null}

          {error ? (
            <div
              className="rounded-lg border border-destructive/35 bg-destructive/10 px-3 py-2.5 text-center text-sm text-destructive"
              role="alert"
            >
              {error}
            </div>
          ) : null}

          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              void handlePasswordLogin()
            }}
            noValidate
          >
            <div
              className={cn(
                devLoginAllowed ? 'border-t border-white/[0.08] pt-6' : '',
              )}
            >
              <p className="mb-4 text-center text-xs font-medium text-muted-foreground sm:text-left">
                {devLoginAllowed
                  ? 'Or sign in with email and password'
                  : 'Use your work email and password.'}
              </p>

              <div className="space-y-3">
                <div>
                  <label className="field-label" htmlFor="login-email">
                    Email
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    autoComplete="email"
                    inputMode="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={pwPending}
                    placeholder="name@company.com"
                    className="field-input"
                  />
                </div>

                <div>
                  <label className="field-label" htmlFor="login-password">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="login-password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={
                        devLoginAllowed
                          ? `Dev default: ${DEV_SEED_PASSWORD}`
                          : '••••••••'
                      }
                      disabled={pwPending}
                      className="field-input pr-11"
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowPassword((s) => !s)}
                      className="absolute right-1.5 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <Button
                type="submit"
                variant="default"
                className="mt-5 w-full"
                disabled={pwPending}
              >
                {pwPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    Signing in…
                  </>
                ) : (
                  'Sign in'
                )}
              </Button>
            </div>
          </form>
        </div>

        <p className="mt-6 text-center text-[0.7rem] leading-relaxed text-muted-foreground/75">
          Secure session · Your credentials are sent over HTTPS only.
        </p>
      </div>
    </div>
  )
}
