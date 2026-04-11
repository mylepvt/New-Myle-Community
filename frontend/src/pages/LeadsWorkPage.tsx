import { type FormEvent, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  LEAD_STATUS_OPTIONS,
  type LeadListFilters,
  type LeadStatus,
  useCreateLeadMutation,
  useDeleteLeadMutation,
  useLeadsQuery,
  usePatchLeadMutation,
} from '@/hooks/use-leads-query'
import { useDashboardShellRole } from '@/hooks/use-dashboard-shell-role'

type Props = {
  title: string
  /** Active = main list (non-archived). Archived = `archived_only` API + restore UX. */
  listMode?: 'active' | 'archived'
}

const emptyFilters: LeadListFilters = { q: '', status: '' }

function statusLabel(value: string): string {
  return LEAD_STATUS_OPTIONS.find((o) => o.value === value)?.label ?? value
}

export function LeadsWorkPage({ title, listMode = 'active' }: Props) {
  const archivedOnly = listMode === 'archived'
  const leadsListMode = listMode === 'archived' ? 'archived' : 'active'
  const { role } = useDashboardShellRole()
  const [searchParams] = useSearchParams()
  const qParam = searchParams.get('q') ?? ''
  const [qInput, setQInput] = useState(qParam)
  const [filters, setFilters] = useState<LeadListFilters>({ ...emptyFilters, q: qParam })
  const [newStatus, setNewStatus] = useState<LeadStatus>('new')
  const [name, setName] = useState('')

  useEffect(() => {
    setQInput(qParam)
  }, [qParam])

  useEffect(() => {
    const id = window.setTimeout(() => {
      setFilters((f) => ({ ...f, q: qInput }))
    }, 400)
    return () => window.clearTimeout(id)
  }, [qInput])

  const { data, isPending, isError, error, refetch } = useLeadsQuery(true, filters, leadsListMode)
  const createMut = useCreateLeadMutation()
  const deleteMut = useDeleteLeadMutation()
  const patchMut = usePatchLeadMutation()

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    try {
      await createMut.mutateAsync({ name: trimmed, status: newStatus })
      setName('')
    } catch {
      /* surfaced below */
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
        {archivedOnly ? (
          <Link
            to="/dashboard/work/leads"
            className="text-sm text-primary underline-offset-2 hover:underline"
          >
            ← Active leads
          </Link>
        ) : (
          <Link
            to="/dashboard/work/archived"
            className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            Archived leads
          </Link>
        )}
      </div>

      {archivedOnly ? (
        <p className="text-sm text-muted-foreground">
          Restore a lead to send it back to your main list and workboard.
        </p>
      ) : null}

      <div className="surface-elevated flex flex-col gap-3 p-4 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="min-w-0 flex-1 sm:min-w-[12rem]">
          <label htmlFor="lead-filter-q" className="mb-1 block text-xs font-medium text-muted-foreground">
            Search name
          </label>
          <input
            id="lead-filter-q"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="Substring match…"
            className="w-full rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
        </div>
        <div className="min-w-[10rem]">
          <label htmlFor="lead-filter-status" className="mb-1 block text-xs font-medium text-muted-foreground">
            Status
          </label>
          <select
            id="lead-filter-status"
            value={filters.status}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                status: e.target.value === '' ? '' : (e.target.value as LeadStatus),
              }))
            }
            className="w-full rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
          >
            <option value="">All</option>
            {LEAD_STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!archivedOnly ? (
        <>
          <form
            onSubmit={(e) => void handleCreate(e)}
            className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end"
          >
            <div className="min-w-0 flex-1">
              <label htmlFor="lead-name" className="mb-1 block text-xs font-medium text-muted-foreground">
                New lead name
              </label>
              <input
                id="lead-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Acme Corp"
                disabled={createMut.isPending}
                className="w-full rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
              />
            </div>
            <div className="min-w-[10rem]">
              <label htmlFor="lead-new-status" className="mb-1 block text-xs font-medium text-muted-foreground">
                Initial status
              </label>
              <select
                id="lead-new-status"
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value as LeadStatus)}
                disabled={createMut.isPending}
                className="w-full rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
              >
                {LEAD_STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" disabled={createMut.isPending || !name.trim()}>
              {createMut.isPending ? 'Adding…' : 'Add lead'}
            </Button>
          </form>
          {createMut.isError ? (
            <p className="text-xs text-destructive" role="alert">
              {createMut.error instanceof Error ? createMut.error.message : 'Could not create'}
            </p>
          ) : null}
        </>
      ) : null}

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : null}
      {isError ? (
        <div className="text-sm text-destructive" role="alert">
          <span>
            {error instanceof Error ? error.message : 'Could not load leads'}{' '}
          </span>
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}
      {data ? (
        <div className="surface-elevated p-4 text-sm text-muted-foreground">
          <p className="mb-3 font-medium text-foreground">
            Total: {data.total}
            {data.total > data.items.length ? (
              <span className="ml-2 font-normal text-muted-foreground">
                (showing {data.items.length}, limit {data.limit}, offset {data.offset})
              </span>
            ) : null}
          </p>
          {data.items.length === 0 ? (
            <p>
              {archivedOnly
                ? 'No archived leads — archive from the active list when you want to clear your pipeline without deleting.'
                : 'No leads match this view — adjust filters or add one above. Non-admin users only see leads they created.'}
            </p>
          ) : (
            <ul className="space-y-2">
              {data.items.map((l) => (
                <li
                  key={l.id}
                  className="surface-inset flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`/dashboard/work/leads/${l.id}`}
                      className="font-medium text-foreground hover:text-primary hover:underline underline-offset-2"
                    >
                      {l.name}
                    </Link>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      #{l.id} · {statusLabel(l.status)} · {new Date(l.created_at).toLocaleString()}
                      {l.archived_at ? (
                        <span className="block text-muted-foreground/90">
                          Archived {new Date(l.archived_at).toLocaleString()}
                        </span>
                      ) : null}
                    </span>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    {!archivedOnly && role === 'admin' ? (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={patchMut.isPending}
                        title="Move to shared pool for members to claim"
                        onClick={() => void patchMut.mutateAsync({ id: l.id, body: { in_pool: true } })}
                      >
                        To pool
                      </Button>
                    ) : null}
                    {!archivedOnly ? (
                      <select
                        aria-label={`Status for ${l.name}`}
                        value={l.status}
                        disabled={patchMut.isPending}
                        onChange={(e) => {
                          const v = e.target.value as LeadStatus
                          void patchMut.mutateAsync({ id: l.id, body: { status: v } })
                        }}
                        className="rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-2 py-1.5 text-xs text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
                      >
                        {LEAD_STATUS_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    ) : null}
                    {archivedOnly ? (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={patchMut.isPending}
                        onClick={() => void patchMut.mutateAsync({ id: l.id, body: { archived: false } })}
                      >
                        Restore
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={patchMut.isPending}
                        onClick={() => void patchMut.mutateAsync({ id: l.id, body: { archived: true } })}
                      >
                        Archive
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      disabled={deleteMut.isPending}
                      onClick={() => void deleteMut.mutateAsync(l.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {deleteMut.isError ? (
            <p className="mt-2 text-xs text-destructive">
              {deleteMut.error instanceof Error ? deleteMut.error.message : 'Delete failed'}
            </p>
          ) : null}
          {patchMut.isError ? (
            <p className="mt-2 text-xs text-destructive">
              {patchMut.error instanceof Error ? patchMut.error.message : 'Update failed'}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
