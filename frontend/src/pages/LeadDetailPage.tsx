import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { LEAD_STATUS_OPTIONS } from '@/hooks/use-leads-query'
import {
  useLeadCallsQuery,
  useLeadDetailQuery,
  useLogCallMutation,
  usePatchLeadDetailMutation,
} from '@/hooks/use-lead-detail-query'

type Props = {
  leadId: number
}

const CALL_OUTCOME_OPTIONS = [
  { value: 'answered', label: 'Answered' },
  { value: 'no_answer', label: 'No Answer' },
  { value: 'busy', label: 'Busy' },
  { value: 'callback_requested', label: 'Callback Requested' },
  { value: 'wrong_number', label: 'Wrong Number' },
]

const CALL_STATUS_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'dnc', label: 'Do Not Call' },
]

function outcomeLabel(v: string): string {
  return CALL_OUTCOME_OPTIONS.find((o) => o.value === v)?.label ?? v
}

function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    new: 'bg-primary/15 text-primary',
    contacted: 'bg-sky-400/15 text-sky-400',
    qualified: 'bg-emerald-400/15 text-emerald-400',
    won: 'bg-[hsl(142_71%_48%)]/15 text-[hsl(142_71%_48%)]',
    lost: 'bg-destructive/15 text-destructive',
  }
  const c = cls[status] ?? 'bg-muted/30 text-muted-foreground'
  const label = LEAD_STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${c}`}>
      {label}
    </span>
  )
}

function PaymentStatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    pending: 'bg-amber-400/15 text-amber-400',
    proof_uploaded: 'bg-sky-400/15 text-sky-400',
    approved: 'bg-[hsl(142_71%_48%)]/15 text-[hsl(142_71%_48%)]',
    rejected: 'bg-destructive/15 text-destructive',
  }
  const labels: Record<string, string> = {
    pending: 'Pending',
    proof_uploaded: 'Proof Uploaded',
    approved: 'Approved ✓',
    rejected: 'Rejected',
  }
  const c = cls[status] ?? 'bg-muted/30 text-muted-foreground'
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${c}`}>
      {labels[status] ?? status}
    </span>
  )
}

export function LeadDetailPage({ leadId }: Props) {
  const { data: lead, isPending, isError, error, refetch } = useLeadDetailQuery(leadId)
  const callsQuery = useLeadCallsQuery(leadId)
  const patchMut = usePatchLeadDetailMutation()
  const logCallMut = useLogCallMutation()

  // Pipeline card local state
  const [pipelineStatus, setPipelineStatus] = useState('')
  const [pipelineCallStatus, setPipelineCallStatus] = useState('')
  const [pipelineError, setPipelineError] = useState('')

  // Notes card
  const [notes, setNotes] = useState('')
  const [notesError, setNotesError] = useState('')
  const notesTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Log call inline form
  const [showCallForm, setShowCallForm] = useState(false)
  const [callOutcome, setCallOutcome] = useState('answered')
  const [callDuration, setCallDuration] = useState('')
  const [callNotes, setCallNotes] = useState('')
  const [callError, setCallError] = useState('')

  // Payment proof URL
  const [showProofInput, setShowProofInput] = useState(false)
  const [proofUrl, setProofUrl] = useState('')
  const [proofError, setProofError] = useState('')

  // Keep local editors in sync when `lead` updates (route change or query refetch after save).
  /* eslint-disable react-hooks/set-state-in-effect -- intentional sync from server record to form state */
  useEffect(() => {
    if (lead) {
      setPipelineStatus(lead.status)
      setPipelineCallStatus(lead.call_status ?? '')
      setNotes(lead.notes ?? '')
      setProofUrl(lead.payment_proof_url ?? '')
    }
  }, [lead])
  /* eslint-enable react-hooks/set-state-in-effect */

  async function savePipeline() {
    if (!lead) return
    setPipelineError('')
    try {
      await patchMut.mutateAsync({
        leadId,
        body: { status: pipelineStatus, call_status: pipelineCallStatus || null },
      })
    } catch (e) {
      setPipelineError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  function handleNotesChange(value: string) {
    setNotes(value)
    setNotesError('')
    if (notesTimer.current) clearTimeout(notesTimer.current)
    notesTimer.current = setTimeout(() => {
      void saveNotes(value)
    }, 1200)
  }

  async function saveNotes(value: string) {
    setNotesError('')
    try {
      await patchMut.mutateAsync({ leadId, body: { notes: value } })
    } catch (e) {
      setNotesError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  async function handleLogCall(e: FormEvent) {
    e.preventDefault()
    setCallError('')
    const dur = callDuration ? parseInt(callDuration, 10) : undefined
    try {
      await logCallMut.mutateAsync({
        leadId,
        body: {
          outcome: callOutcome,
          duration_seconds: dur,
          notes: callNotes.trim() || undefined,
        },
      })
      setShowCallForm(false)
      setCallOutcome('answered')
      setCallDuration('')
      setCallNotes('')
    } catch (e) {
      setCallError(e instanceof Error ? e.message : 'Could not log call')
    }
  }

  async function handleSaveProof(e: FormEvent) {
    e.preventDefault()
    setProofError('')
    try {
      await patchMut.mutateAsync({ leadId, body: { payment_proof_url: proofUrl || null } })
      setShowProofInput(false)
    } catch (e) {
      setProofError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  async function toggleDayCompleted(
    field: 'day1_completed_at' | 'day2_completed_at' | 'day3_completed_at',
    current: string | null,
  ) {
    try {
      await patchMut.mutateAsync({
        leadId,
        body: { [field]: current ? null : new Date().toISOString() },
      })
    } catch {
      /* surfaced by patchMut.isError */
    }
  }

  async function toggleWhatsapp(current: string | null) {
    try {
      await patchMut.mutateAsync({
        leadId,
        body: { whatsapp_sent_at: current ? null : new Date().toISOString() },
      })
    } catch {
      /* surfaced by patchMut.isError */
    }
  }

  if (isPending) {
    return (
      <div className="max-w-4xl space-y-4 p-4" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="max-w-4xl space-y-4 p-4">
        <p className="text-sm text-destructive" role="alert">
          {error instanceof Error ? error.message : 'Could not load lead'}
        </p>
        <Button variant="secondary" size="sm" onClick={() => void refetch()}>
          Retry
        </Button>
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="max-w-4xl p-4">
        <p className="text-sm text-muted-foreground">Lead not found.</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/dashboard/work/leads"
            className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            ← All leads
          </Link>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{lead.name}</h1>
          <StatusBadge status={lead.status} />
        </div>
        <Button variant="secondary" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* LEFT COLUMN */}
        <div className="space-y-4">
          {/* Contact card */}
          <div className="surface-elevated p-4 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Contact</p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-14 shrink-0">Phone</span>
                {lead.phone ? (
                  <>
                    <span className="text-foreground">{lead.phone}</span>
                    <button
                      type="button"
                      className="text-xs text-primary underline-offset-2 hover:underline"
                      onClick={() => void navigator.clipboard.writeText(lead.phone ?? '')}
                    >
                      Copy
                    </button>
                  </>
                ) : (
                  <span className="text-muted-foreground/60">—</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-14 shrink-0">Email</span>
                {lead.email ? (
                  <span className="text-foreground break-all">{lead.email}</span>
                ) : (
                  <span className="text-muted-foreground/60">—</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-14 shrink-0">City</span>
                <span className="text-foreground">{lead.city ?? '—'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-14 shrink-0">Source</span>
                <span className="text-foreground">{lead.source ?? '—'}</span>
              </div>
            </div>
          </div>

          {/* Pipeline card */}
          <div className="surface-elevated p-4 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Pipeline</p>
            <div className="space-y-3">
              <div>
                <label
                  htmlFor="pipeline-status"
                  className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                >
                  Status
                </label>
                <select
                  id="pipeline-status"
                  value={pipelineStatus}
                  onChange={(e) => setPipelineStatus(e.target.value)}
                  className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
                >
                  {LEAD_STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label
                  htmlFor="pipeline-call-status"
                  className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                >
                  Call status
                </label>
                <select
                  id="pipeline-call-status"
                  value={pipelineCallStatus}
                  onChange={(e) => setPipelineCallStatus(e.target.value)}
                  className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
                >
                  {CALL_STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                type="button"
                size="sm"
                disabled={patchMut.isPending}
                onClick={() => void savePipeline()}
              >
                {patchMut.isPending ? 'Saving…' : 'Save pipeline'}
              </Button>
              {pipelineError ? (
                <p className="text-xs text-destructive">{pipelineError}</p>
              ) : null}
            </div>
          </div>

          {/* Timeline card */}
          <div className="surface-elevated p-4 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Timeline</p>
            <div className="space-y-2">
              {(
                [
                  ['day1_completed_at', 'Day 1 completed'],
                  ['day2_completed_at', 'Day 2 completed'],
                  ['day3_completed_at', 'Day 3 completed'],
                ] as const
              ).map(([field, label]) => (
                <label key={field} className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!!lead[field]}
                    disabled={patchMut.isPending}
                    onChange={() => void toggleDayCompleted(field, lead[field])}
                    className="h-4 w-4 rounded border-white/12 bg-white/[0.05] accent-primary"
                  />
                  <span className="text-foreground">{label}</span>
                  {lead[field] ? (
                    <span className="text-xs text-muted-foreground">
                      {new Date(lead[field]!).toLocaleDateString()}
                    </span>
                  ) : null}
                </label>
              ))}
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={!!lead.whatsapp_sent_at}
                  disabled={patchMut.isPending}
                  onChange={() => void toggleWhatsapp(lead.whatsapp_sent_at)}
                  className="h-4 w-4 rounded border-white/12 bg-white/[0.05] accent-primary"
                />
                <span className="text-foreground">WhatsApp sent</span>
                {lead.whatsapp_sent_at ? (
                  <span className="text-xs text-muted-foreground">
                    {new Date(lead.whatsapp_sent_at).toLocaleDateString()}
                  </span>
                ) : null}
              </label>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div className="space-y-4">
          {/* Call log card */}
          <div className="surface-elevated p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Call log
                {lead.call_count > 0 ? (
                  <span className="ml-1.5 normal-case">({lead.call_count})</span>
                ) : null}
              </p>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setShowCallForm((v) => !v)}
              >
                {showCallForm ? 'Cancel' : '+ Log call'}
              </Button>
            </div>

            {showCallForm ? (
              <form onSubmit={(e) => void handleLogCall(e)} className="surface-inset space-y-3 p-3">
                <div>
                  <label
                    htmlFor="call-outcome"
                    className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    Outcome
                  </label>
                  <select
                    id="call-outcome"
                    value={callOutcome}
                    onChange={(e) => setCallOutcome(e.target.value)}
                    className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
                  >
                    {CALL_OUTCOME_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="call-duration"
                    className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    Duration (seconds, optional)
                  </label>
                  <input
                    id="call-duration"
                    type="number"
                    min="0"
                    value={callDuration}
                    onChange={(e) => setCallDuration(e.target.value)}
                    className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
                    placeholder="e.g. 120"
                  />
                </div>
                <div>
                  <label
                    htmlFor="call-notes"
                    className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    Notes (optional)
                  </label>
                  <textarea
                    id="call-notes"
                    value={callNotes}
                    onChange={(e) => setCallNotes(e.target.value)}
                    rows={2}
                    className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35 resize-none"
                    placeholder="What was discussed…"
                  />
                </div>
                {callError ? (
                  <p className="text-xs text-destructive">{callError}</p>
                ) : null}
                <Button type="submit" size="sm" disabled={logCallMut.isPending}>
                  {logCallMut.isPending ? 'Logging…' : 'Log call'}
                </Button>
              </form>
            ) : null}

            {callsQuery.isPending ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : null}

            {callsQuery.data && callsQuery.data.items.length === 0 ? (
              <p className="text-sm text-muted-foreground">No calls logged yet.</p>
            ) : null}

            {callsQuery.data && callsQuery.data.items.length > 0 ? (
              <ul className="space-y-2">
                {callsQuery.data.items.map((c) => (
                  <li key={c.id} className="surface-inset px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-1">
                      <span className="font-medium text-foreground">{outcomeLabel(c.outcome)}</span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(c.called_at).toLocaleString()}
                      </span>
                    </div>
                    {c.duration_seconds != null ? (
                      <p className="text-xs text-muted-foreground">{c.duration_seconds}s</p>
                    ) : null}
                    {c.notes ? (
                      <p className="mt-0.5 text-xs text-muted-foreground">{c.notes}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          {/* Notes card */}
          <div className="surface-elevated p-4 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Notes</p>
            <textarea
              value={notes}
              onChange={(e) => handleNotesChange(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35 resize-none"
              placeholder="Add notes about this lead…"
            />
            <div className="flex items-center gap-3">
              <Button
                type="button"
                size="sm"
                disabled={patchMut.isPending}
                onClick={() => void saveNotes(notes)}
              >
                {patchMut.isPending ? 'Saving…' : 'Save notes'}
              </Button>
              {notesError ? (
                <p className="text-xs text-destructive">{notesError}</p>
              ) : null}
            </div>
          </div>

          {/* Payment card */}
          <div className="surface-elevated p-4 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Payment</p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-20 shrink-0">Status</span>
                {lead.payment_status ? (
                  <PaymentStatusBadge status={lead.payment_status} />
                ) : (
                  <span className="text-muted-foreground/60">—</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-20 shrink-0">Amount</span>
                {lead.payment_amount_cents != null ? (
                  <span className="text-foreground">
                    ₹{(lead.payment_amount_cents / 100).toFixed(2)}
                  </span>
                ) : (
                  <span className="text-muted-foreground/60">—</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-20 shrink-0">Proof</span>
                {lead.payment_proof_url ? (
                  <a
                    href={lead.payment_proof_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline-offset-2 hover:underline text-xs break-all"
                  >
                    View proof
                  </a>
                ) : (
                  <span className="text-muted-foreground/60">—</span>
                )}
              </div>
            </div>

            {showProofInput ? (
              <form
                onSubmit={(e) => void handleSaveProof(e)}
                className="surface-inset space-y-2 p-3"
              >
                <label
                  htmlFor="proof-url"
                  className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
                >
                  Proof URL
                </label>
                <input
                  id="proof-url"
                  type="url"
                  value={proofUrl}
                  onChange={(e) => setProofUrl(e.target.value)}
                  placeholder="https://…"
                  className="w-full rounded-md border border-white/12 bg-white/[0.05] px-3 py-2 text-sm text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/35"
                />
                {proofError ? (
                  <p className="text-xs text-destructive">{proofError}</p>
                ) : null}
                <div className="flex gap-2">
                  <Button type="submit" size="sm" disabled={patchMut.isPending}>
                    {patchMut.isPending ? 'Saving…' : 'Save'}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowProofInput(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setShowProofInput(true)}
              >
                Upload proof URL
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
