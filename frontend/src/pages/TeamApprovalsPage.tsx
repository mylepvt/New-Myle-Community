import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/components/ui/states'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiFetch } from '@/lib/api'

type PendingRow = {
  id: number
  fbo_id: string
  username: string | null
  email: string
  phone: string | null
  created_at: string
}

type Props = {
  title: string
}

export function TeamApprovalsPage({ title }: Props) {
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: ['team', 'pending-registrations'],
    queryFn: async () => {
      const r = await apiFetch('/api/v1/team/pending-registrations')
      if (!r.ok) {
        const t = await r.text()
        throw new Error(t || r.statusText)
      }
      return r.json() as Promise<{ items: PendingRow[]; total: number }>
    },
  })

  const decide = useMutation({
    mutationFn: async (vars: { id: number; action: 'approve' | 'reject' }) => {
      const r = await apiFetch(
        `/api/v1/team/pending-registrations/${vars.id}/decision`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: vars.action }),
        },
      )
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        const msg =
          typeof err === 'object' && err !== null && 'detail' in err
            ? String((err as { detail?: string }).detail)
            : await r.text()
        throw new Error(msg || r.statusText)
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['team', 'pending-registrations'] })
    },
  })

  return (
    <div className="max-w-4xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        Self-serve registrations pending admin approval (legacy parity). Rejected users cannot sign
        in; approved users can log in with the password they set at registration.
      </p>

      {q.isPending ? <LoadingState label="Loading pending registrations" /> : null}
      {q.isError ? (
        <ErrorState message={q.error instanceof Error ? q.error.message : 'Failed to load'} />
      ) : null}

      {q.data ? (
        q.data.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No pending registrations.</p>
        ) : (
          <div className="surface-elevated overflow-hidden rounded-xl border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>FBO ID</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.items.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-mono text-xs">{row.fbo_id}</TableCell>
                    <TableCell>{row.username ?? '—'}</TableCell>
                    <TableCell className="text-xs">{row.email}</TableCell>
                    <TableCell className="text-xs">{row.phone ?? '—'}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          disabled={decide.isPending}
                          onClick={() => decide.mutate({ id: row.id, action: 'reject' })}
                        >
                          Reject
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          disabled={decide.isPending}
                          onClick={() => decide.mutate({ id: row.id, action: 'approve' })}
                        >
                          Approve
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )
      ) : null}
    </div>
  )
}
