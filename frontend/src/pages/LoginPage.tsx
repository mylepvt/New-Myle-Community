import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { authDevLogin } from '@/lib/auth-api'
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
          {pending ? '…' : 'Continue'}
        </Button>
      </div>
    </div>
  )
}
