import { Link } from 'react-router-dom'

import { LEAD_STATUS_OPTIONS } from '@/hooks/use-leads-query'

type Props = {
  title: string
}

/**
 * Read-only pipeline — statuses match API (`Lead.status`). Editing happens on Leads / Workboard.
 */
export function LeadFlowPage({ title }: Props) {
  const mainline = ['new', 'contacted', 'qualified'] as const
  const terminals = ['won', 'lost'] as const

  function label(v: string): string {
    return LEAD_STATUS_OPTIONS.find((o) => o.value === v)?.label ?? v
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        Default path for a lead. Actual moves are done on{' '}
        <Link to="/dashboard/work/leads" className="text-primary underline-offset-2 hover:underline">
          My Leads
        </Link>{' '}
        or the{' '}
        <Link to="/dashboard/work/workboard" className="text-primary underline-offset-2 hover:underline">
          Workboard
        </Link>
        .
      </p>

      <div className="rounded-lg border border-white/10 bg-card/40 p-4">
        <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Pipeline</p>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {mainline.map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              <span className="rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 font-medium text-primary">
                {label(s)}
              </span>
              {i < mainline.length - 1 ? (
                <span className="text-muted-foreground" aria-hidden>
                  →
                </span>
              ) : null}
            </span>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-white/10 pt-4">
          <span className="text-xs text-muted-foreground">Outcomes:</span>
          {terminals.map((s) => (
            <span
              key={s}
              className="rounded-md border border-white/15 bg-background/50 px-3 py-1.5 text-foreground"
            >
              {label(s)}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
