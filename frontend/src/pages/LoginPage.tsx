import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { authDevLogin, authPasswordLogin, DEV_SEED_PASSWORD } from '@/lib/auth-api'
import { fetchAuthMe } from '@/hooks/use-auth-me-query'
import { DEFAULT_META, useMetaQuery } from '@/hooks/use-meta-query'
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
  const [email, setEmail] = useState('dev-leader@myle.local')
  const [password, setPassword] = useState('')
  const [pwPending, setPwPending] = useState(false)

  async function handlePasswordLogin() {
    setError(null)
    if (!password.trim()) {
      setError(
        devLoginAllowed
          ? `Password required — dev seed: ${DEV_SEED_PASSWORD}`
          : 'Password required',
      )
      return
    }
    setPwPending(true)
    try {
      await authPasswordLogin(email, password)
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
    <div className="flex min-h-dvh flex-col items-center justify-center p-6">
      <div className="surface-elevated w-full max-w-sm space-y-6 rounded-2xl p-8">
        <h1 className="bg-gradient-to-br from-foreground via-foreground to-primary/85 bg-clip-text text-center text-2xl font-semibold tracking-tight text-transparent">
          Myle vl2
        </h1>
        {devLoginAllowed ? (
          <>
            <label className="sr-only" htmlFor="login-role">
              Role
            </label>
            <select
              id="login-role"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              disabled={pending}
              className="w-full rounded-lg border border-white/[0.1] bg-black/25 px-3 py-2.5 text-sm text-foreground shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus:ring-2 focus:ring-primary/35"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <Button
              type="button"
              className="w-full"
              disabled={pending}
              onClick={() => void handleContinue()}
            >
              {pending ? '…' : 'Continue (dev role)'}
            </Button>
          </>
        ) : null}

        {error ? (
          <p className="text-center text-xs text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        <div className={devLoginAllowed ? 'border-t border-white/[0.08] pt-6' : 'pt-1'}>
          <p className="mb-3 text-center text-xs font-medium text-muted-foreground">
            {devLoginAllowed ? 'Or sign in with email + password' : 'Sign in with email + password'}
          </p>
          <label className="sr-only" htmlFor="login-email">
            Email
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={pwPending}
            className="mb-2 w-full rounded-lg border border-white/[0.1] bg-black/25 px-3 py-2.5 text-sm text-foreground shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
          <label className="sr-only" htmlFor="login-password">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={devLoginAllowed ? `Dev default: ${DEV_SEED_PASSWORD}` : 'Password'}
            disabled={pwPending}
            className="mb-3 w-full rounded-lg border border-white/[0.1] bg-black/25 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/70 shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
          <Button
            type="button"
            variant="secondary"
            className="w-full"
            disabled={pwPending}
            onClick={() => void handlePasswordLogin()}
          >
            {pwPending ? '…' : 'Sign in'}
          </Button>
        </div>
      </div>
    </div>
  )
}
