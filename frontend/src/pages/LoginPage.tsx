import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { authDevLogin, authPasswordLogin, DEV_SEED_PASSWORD } from '@/lib/auth-api'
import { useAuthStore } from '@/stores/auth-store'
import { useRoleStore } from '@/stores/role-store'
import { ROLES, type Role } from '@/types/role'

export function LoginPage() {
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
    setPwPending(true)
    try {
      await authPasswordLogin(email, password)
      login()
      await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
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
      login()
      await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
      navigate(from, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign-in failed')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-6 rounded-2xl border border-white/10 bg-card/80 p-8 shadow-2xl shadow-black/40 backdrop-blur-xl">
        <h1 className="bg-gradient-to-br from-foreground via-foreground to-primary/90 bg-clip-text text-center text-2xl font-semibold tracking-tight text-transparent">
          Myle vl2
        </h1>
        <label className="sr-only" htmlFor="login-role">
          Role
        </label>
        <select
          id="login-role"
          value={role}
          onChange={(e) => setRole(e.target.value as Role)}
          disabled={pending}
          className="w-full rounded-md border border-white/10 bg-card/80 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        {error ? (
          <p className="text-center text-xs text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <Button
          type="button"
          className="w-full"
          disabled={pending}
          onClick={() => void handleContinue()}
        >
          {pending ? '…' : 'Continue (dev role)'}
        </Button>

        <div className="border-t border-white/10 pt-6">
          <p className="mb-3 text-center text-xs font-medium text-muted-foreground">
            Or sign in with email + password
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
            className="mb-2 w-full rounded-md border border-white/10 bg-card/80 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
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
            placeholder={`Dev default: ${DEV_SEED_PASSWORD}`}
            disabled={pwPending}
            className="mb-3 w-full rounded-md border border-white/10 bg-card/80 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
          <Button
            type="button"
            variant="secondary"
            className="w-full"
            disabled={pwPending || !password.trim()}
            onClick={() => void handlePasswordLogin()}
          >
            {pwPending ? '…' : 'Sign in'}
          </Button>
        </div>
      </div>
    </div>
  )
}
