import { type FormEvent, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useCreateFollowUpMutation,
  useDeleteFollowUpMutation,
  useFollowUpsQuery,
  usePatchFollowUpMutation,
} from '@/hooks/use-follow-ups-query'
import { useLeadsQuery } from '@/hooks/use-leads-query'

type Props = {
  title: string
}

const emptyLeadFilters = { q: '', status: '' as const }

export function FollowUpsWorkPage({ title }: Props) {
  const [openOnly, setOpenOnly] = useState(true)
  const [leadId, setLeadId] = useState('')
  const [note, setNote] = useState('')
  const [dueLocal, setDueLocal] = useState('')

  const leadsQ = useLeadsQuery(true, emptyLeadFilters, 'active')
  const fuQ = useFollowUpsQuery(openOnly)
  const createMut = useCreateFollowUpMutation()
  const patchMut = usePatchFollowUpMutation()
  const delMut = useDeleteFollowUpMutation()

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    const lid = Number(leadId)
    const trimmed = note.trim()
    if (!lid || !trimmed) return
    let due_at: string | undefined
    if (dueLocal) {
      due_at = new Date(dueLocal).toISOString()
    }
    try {
      await createMut.mutateAsync({ lead_id: lid, note: trimmed, due_at })
      setNote('')
      setDueLocal('')
    } catch {
      /* below */
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        Follow-ups are tied to leads you can access (same rules as My Leads). Mark done or reopen anytime.
      </p>

      <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
        <input
          type="checkbox"
          checked={openOnly}
          onChange={(e) => setOpenOnly(e.target.checked)}
          className="rounded border-white/20 bg-card"
        />
        Open only (hide completed)
      </label>

      <form onSubmit={(e) => void handleCreate(e)} className="surface-elevated space-y-3 p-4">
        <p className="text-xs font-medium text-muted-foreground">New follow-up</p>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <div className="min-w-[10rem] flex-1">
            <label htmlFor="fu-lead" className="mb-1 block text-xs text-muted-foreground">
              Lead
            </label>
            <select
              id="fu-lead"
              value={leadId}
              onChange={(e) => setLeadId(e.target.value)}
              disabled={leadsQ.isPending || createMut.isPending}
              className="w-full rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
            >
              <option value="">Select lead…</option>
              {(leadsQ.data?.items ?? []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name} (#{l.id})
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[10rem] flex-1">
            <label htmlFor="fu-due" className="mb-1 block text-xs text-muted-foreground">
              Due (optional)
            </label>
            <input
              id="fu-due"
              type="datetime-local"
              value={dueLocal}
              onChange={(e) => setDueLocal(e.target.value)}
              className="w-full rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
            />
          </div>
        </div>
        <div>
          <label htmlFor="fu-note" className="mb-1 block text-xs text-muted-foreground">
            Note
          </label>
          <textarea
            id="fu-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder="What to do next…"
            className="w-full rounded-md border border-white/12 bg-white/[0.05] backdrop-blur-sm px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
          />
        </div>
        <Button type="submit" disabled={createMut.isPending || !leadId || !note.trim()}>
          {createMut.isPending ? 'Saving…' : 'Add follow-up'}
        </Button>
        {createMut.isError ? (
          <p className="text-xs text-destructive" role="alert">
            {createMut.error instanceof Error ? createMut.error.message : 'Could not create'}
          </p>
        ) : null}
      </form>

      {fuQ.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : null}
      {fuQ.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {fuQ.error instanceof Error ? fuQ.error.message : 'Could not load'}
        </p>
      ) : null}

      {fuQ.data ? (
        <div className="surface-elevated p-4 text-sm">
          <p className="mb-3 font-medium text-foreground">
            Total: {fuQ.data.total}
            {fuQ.data.total > fuQ.data.items.length ? (
              <span className="ml-2 font-normal text-muted-foreground">
                (showing {fuQ.data.items.length})
              </span>
            ) : null}
          </p>
          {fuQ.data.items.length === 0 ? (
            <p className="text-muted-foreground">No follow-ups in this view.</p>
          ) : (
            <ul className="space-y-2">
              {fuQ.data.items.map((f) => (
                <li
                  key={f.id}
                  className="surface-inset px-3 py-2 text-muted-foreground"
                >
                  <p className="font-medium text-foreground">{f.note}</p>
                  <p className="mt-1 text-xs">
                    {f.lead_name} · #{f.lead_id}
                    {f.due_at ? ` · due ${new Date(f.due_at).toLocaleString()}` : ''}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {f.completed_at ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={patchMut.isPending}
                        onClick={() => void patchMut.mutateAsync({ id: f.id, body: { completed: false } })}
                      >
                        Reopen
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={patchMut.isPending}
                        onClick={() => void patchMut.mutateAsync({ id: f.id, body: { completed: true } })}
                      >
                        Done
                      </Button>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="text-destructive"
                      disabled={delMut.isPending}
                      onClick={() => void delMut.mutateAsync(f.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}
