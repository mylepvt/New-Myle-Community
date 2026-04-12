import { Link } from 'react-router-dom'
import { CheckCircle2, CircleAlert, ShieldCheck } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useGateAssistantQuery } from '@/hooks/use-gate-assistant-query'
import { cn } from '@/lib/utils'

type Props = {
  sessionReady: boolean
}

function riskStyles(level: 'green' | 'yellow' | 'red') {
  switch (level) {
    case 'red':
      return 'border-l-destructive bg-destructive/[0.06]'
    case 'yellow':
      return 'border-l-warning bg-warning/[0.06]'
    default:
      return 'border-l-success bg-success/[0.05]'
  }
}

function riskLabel(level: 'green' | 'yellow' | 'red') {
  switch (level) {
    case 'red':
      return 'Needs attention'
    case 'yellow':
      return 'In progress'
    default:
      return 'On track'
  }
}

export function GateAssistantCard({ sessionReady }: Props) {
  const { data, isPending, isError, error, refetch } = useGateAssistantQuery(sessionReady)

  if (!sessionReady) {
    return null
  }

  if (isPending) {
    return (
      <Card className="border-primary/20">
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-3 w-full max-w-md" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (isError || !data) {
    return (
      <Card className="border-destructive/30">
        <CardHeader>
          <CardTitle className="text-ds-h3">Gate Assistant</CardTitle>
          <CardDescription className="text-destructive">
            {error instanceof Error ? error.message : 'Could not load'}{' '}
            <button
              type="button"
              className="font-medium underline underline-offset-2"
              onClick={() => void refetch()}
            >
              Retry
            </button>
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const pct =
    data.progress_total > 0
      ? Math.round((data.progress_done / data.progress_total) * 100)
      : 0

  return (
    <Card
      className={cn(
        'overflow-hidden border border-border/80 border-l-4 shadow-sm',
        riskStyles(data.risk_level),
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-primary" aria-hidden />
            <CardTitle className="text-ds-h3">Gate Assistant</CardTitle>
          </div>
          <span
            className={cn(
              'rounded-full border px-2.5 py-0.5 text-ds-caption font-semibold',
              data.risk_level === 'red' && 'border-destructive/40 text-destructive',
              data.risk_level === 'yellow' && 'border-warning/50 text-warning',
              data.risk_level === 'green' && 'border-success/40 text-success',
            )}
          >
            {riskLabel(data.risk_level)}
          </span>
        </div>
        <CardDescription>
          Daily focus — follow-ups and pipeline health (from your live data).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {pct < 100 ? (
          <div>
            <div className="mb-1 flex justify-between text-ds-caption text-muted-foreground">
              <span>Checklist</span>
              <span>
                {data.progress_done} / {data.progress_total}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted/60">
              <div
                className="h-full rounded-full bg-primary transition-[width]"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        ) : null}

        <ul className="space-y-2 text-sm">
          {data.checklist.map((c) => (
            <li key={c.id} className="flex items-start gap-2">
              {c.done ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
              ) : (
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
              )}
              <span className={cn(c.done ? 'text-muted-foreground' : 'text-foreground')}>
                {c.label}
              </span>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap gap-2">
          <Button variant="default" size="sm" asChild>
            <Link to="/dashboard/work/follow-ups">View queue</Link>
          </Button>
          {data.next_href ? (
            <Button variant="outline" size="sm" asChild>
              <Link to={`/dashboard/${data.next_href}`}>Open follow-ups</Link>
            </Button>
          ) : null}
        </div>

        <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm">
          <p className="font-medium text-foreground">{data.next_action}</p>
          <p className="mt-1 text-ds-caption text-muted-foreground">
            Open: {data.open_follow_ups} · Overdue: {data.overdue_follow_ups} · Pipeline leads:{' '}
            {data.active_pipeline_leads}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
