import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { createTeamMember, useTeamMembersQuery } from '@/hooks/use-team-query'
import { ROLES, type Role } from '@/types/role'

type Props = { title: string }

export function TeamMembersPage({ title }: Props) {
  const queryClient = useQueryClient()
  const { data: me } = useAuthMeQuery()
  const isAdmin = me?.authenticated && me.role === 'admin'
  const { data, isPending, isError, error, refetch } = useTeamMembersQuery()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newRole, setNewRole] = useState<Role>('team')
  const [createError, setCreateError] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: createTeamMember,
    onSuccess: async () => {
      setCreateError(null)
      setEmail('')
      setPassword('')
      await queryClient.invalidateQueries({ queryKey: ['team', 'members'] })
    },
    onError: (e: Error) => setCreateError(e.message),
  })

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        All accounts in this environment (from the users table). Passwords are never exposed via this API.
      </p>

      {isAdmin ? (
        <div className="surface-elevated p-5 text-sm">
          <h2 className="mb-3 font-medium text-foreground">Add user</h2>
          <p className="mb-3 text-xs text-muted-foreground">
            Creates a password-login account (min. 8 characters). Admin only.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
            <label className="block min-w-[12rem] flex-1">
              <span className="mb-1 block text-xs text-muted-foreground">Email</span>
              <input
                type="email"
                autoComplete="off"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={createMut.isPending}
                className="w-full rounded-lg border border-white/[0.1] bg-black/20 px-3 py-2.5 text-foreground shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus:ring-2 focus:ring-primary/35"
              />
            </label>
            <label className="block min-w-[10rem] flex-1">
              <span className="mb-1 block text-xs text-muted-foreground">Password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={createMut.isPending}
                className="w-full rounded-lg border border-white/[0.1] bg-black/20 px-3 py-2.5 text-foreground shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus:ring-2 focus:ring-primary/35"
              />
            </label>
            <label className="block w-full min-w-[8rem] sm:w-auto">
              <span className="mb-1 block text-xs text-muted-foreground">Role</span>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as Role)}
                disabled={createMut.isPending}
                className="w-full rounded-lg border border-white/[0.1] bg-black/20 px-3 py-2.5 text-foreground shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)] focus:outline-none focus:ring-2 focus:ring-primary/35 sm:w-36"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            <Button
              type="button"
              disabled={createMut.isPending || !email.trim() || password.length < 8}
              onClick={() =>
                createMut.mutate({
                  email: email.trim(),
                  password,
                  role: newRole,
                })
              }
            >
              {createMut.isPending ? '…' : 'Create'}
            </Button>
          </div>
          {createError ? (
            <p className="mt-2 text-xs text-destructive" role="alert">
              {createError}
            </p>
          ) : null}
        </div>
      ) : null}

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
        <div className="surface-elevated p-5 text-sm">
          <p className="mb-3 font-medium text-foreground">Total: {data.total}</p>
          <ul className="space-y-2">
            {data.items.map((m) => (
              <li
                key={m.id}
                className="surface-inset px-3 py-2.5 text-muted-foreground"
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
