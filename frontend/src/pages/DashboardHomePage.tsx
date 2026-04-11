import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, TrendingUp } from 'lucide-react'

import { GateAssistantCard } from '@/components/dashboard/GateAssistantCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, LoadingState } from '@/components/ui/states'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DASHBOARD_HOME_OVERVIEW_TITLE,
  getHomeQuickActions,
} from '@/config/dashboard-home-actions'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { useDashboardShellRole } from '@/hooks/use-dashboard-shell-role'
import { useFollowUpsQuery } from '@/hooks/use-follow-ups-query'
import { useLeadPoolQuery } from '@/hooks/use-lead-pool-query'
import { LEAD_STATUS_OPTIONS, type LeadPublic } from '@/hooks/use-leads-query'
import { DEFAULT_META, useMetaQuery } from '@/hooks/use-meta-query'
import { useWorkboardQuery } from '@/hooks/use-workboard-query'
import { t } from '@/lib/i18n'

function statusLabel(status: string): string {
  return LEAD_STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status
}

function recentFromWorkboard(columns: { items: LeadPublic[] }[] | undefined): LeadPublic[] {
  if (!columns?.length) return []
  const seen = new Set<number>()
  const out: LeadPublic[] = []
  for (const col of columns) {
    for (const item of col.items) {
      if (!seen.has(item.id)) {
        seen.add(item.id)
        out.push(item)
      }
    }
  }
  return out
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
    .slice(0, 8)
}

export function DashboardHomePage() {
  const { role, isPending: rolePending } = useDashboardShellRole()
  const { data: me, isPending: mePending } = useAuthMeQuery()
  const { data: meta } = useMetaQuery()
  const navFlags = useMemo(
    () => ({
      intelligence:
        meta?.features.intelligence ?? DEFAULT_META.features.intelligence,
    }),
    [meta?.features.intelligence],
  )
  const sessionReady = Boolean(me?.authenticated)

  const wb = useWorkboardQuery(sessionReady)
  const fu = useFollowUpsQuery(true, sessionReady)
  const pool = useLeadPoolQuery(sessionReady)

  const firstName =
    me?.email?.split('@')[0]?.split(/[._-]/)[0] ?? 'there'

  const metrics = useMemo(() => {
    const columns = wb.data?.columns
    if (!columns) {
      return {
        pipelineTotal: 0,
        won: 0,
        lost: 0,
        newLeads: 0,
        winRatePct: null as number | null,
        chartMax: 1,
        bars: [] as { status: string; total: number; label: string }[],
      }
    }
    let pipelineTotal = 0
    let won = 0
    let lost = 0
    let newLeads = 0
    const bars: { status: string; total: number; label: string }[] = []
    for (const c of columns) {
      pipelineTotal += c.total
      if (c.status === 'won') won = c.total
      if (c.status === 'lost') lost = c.total
      if (c.status === 'new') newLeads = c.total
      bars.push({
        status: c.status,
        total: c.total,
        label: statusLabel(c.status),
      })
    }
    const closed = won + lost
    const winRatePct = closed > 0 ? Math.round((won / closed) * 100) : null
    const chartMax = Math.max(...bars.map((b) => b.total), 1)
    return {
      pipelineTotal,
      won,
      lost,
      newLeads,
      winRatePct,
      chartMax,
      bars,
    }
  }, [wb.data?.columns])

  const recentLeads = useMemo(
    () => recentFromWorkboard(wb.data?.columns),
    [wb.data?.columns],
  )

  const openFollowUps = fu.data?.total ?? 0
  const poolTotal = pool.data?.total ?? 0

  const kpiLoading = sessionReady && (wb.isPending || fu.isPending)

  const quickActions = useMemo(() => {
    if (role == null) return []
    return getHomeQuickActions(role, navFlags, { poolTotal })
  }, [role, navFlags, poolTotal])

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Card className="overflow-hidden border-primary/25 bg-gradient-to-br from-card via-card to-primary/[0.06]">
        <CardHeader className="flex flex-row items-start justify-between gap-4 pb-2">
          <div>
            <CardDescription>Today · {meta?.environment ?? '…'}</CardDescription>
            <CardTitle className="mt-1 font-heading text-ds-h1 capitalize tracking-tight">
              Welcome, {firstName}!
            </CardTitle>
            <p className="mt-2 max-w-xl text-ds-body text-muted-foreground">
              {rolePending && role == null ? (
                <span className="inline-block h-4 w-48 animate-pulse rounded bg-muted/60" />
              ) : (
                <>
                  {role != null ? DASHBOARD_HOME_OVERVIEW_TITLE[role] : 'Dashboard'} —{' '}
                  {t('appTagline')}
                </>
              )}
            </p>
            {me?.email ? (
              <p className="mt-1 text-ds-caption text-subtle">{me.email}</p>
            ) : null}
          </div>
          <div className="hidden shrink-0 rounded-2xl border border-primary/20 bg-primary/10 p-3 text-primary sm:block">
            <TrendingUp className="size-10" strokeWidth={1.25} aria-hidden />
          </div>
        </CardHeader>
      </Card>

      <GateAssistantCard sessionReady={sessionReady} />

      {wb.isError ? (
        <ErrorState
          message={
            wb.error instanceof Error
              ? wb.error.message
              : 'Could not load pipeline data.'
          }
          onRetry={() => void wb.refetch()}
        />
      ) : null}

      <div>
        <h2 className="mb-3 font-heading text-ds-h2 text-foreground">
          Overview
        </h2>
        {kpiLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="border-primary/20">
                <CardContent className="pt-6">
                  <Skeleton className="mb-2 h-3 w-24" />
                  <Skeleton className="h-8 w-16" />
                  <Skeleton className="mt-2 h-3 w-20" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Link
              to="/dashboard/work/workboard"
              className="block rounded-xl no-underline outline-none ring-offset-background transition hover:opacity-95 focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2"
            >
              <Card className="h-full border-primary/20 transition-colors hover:border-primary/35">
                <CardContent className="pt-6">
                  <p className="text-ds-caption font-medium uppercase tracking-wide text-muted-foreground">
                    Active pipeline
                  </p>
                  <p className="mt-2 font-heading text-3xl font-semibold tabular-nums text-foreground">
                    {metrics.pipelineTotal}
                  </p>
                  <p className="mt-1 text-ds-caption text-subtle">
                    Leads in your scope (excl. pool / archive) — open workboard
                  </p>
                </CardContent>
              </Card>
            </Link>
            {role === 'admin' || role === 'leader' ? (
              <Link
                to="/dashboard/work/follow-ups"
                className="block rounded-xl no-underline outline-none ring-offset-background transition hover:opacity-95 focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2"
              >
                <Card className="h-full border-primary/20 transition-colors hover:border-primary/35">
                  <CardContent className="pt-6">
                    <p className="text-ds-caption font-medium uppercase tracking-wide text-muted-foreground">
                      Open follow-ups
                    </p>
                    <p className="mt-2 font-heading text-3xl font-semibold tabular-nums text-primary">
                      {openFollowUps}
                    </p>
                    <p className="mt-1 text-ds-caption text-subtle">
                      Not completed — open queue
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ) : (
              <Card className="border-primary/20">
                <CardContent className="pt-6">
                  <p className="text-ds-caption font-medium uppercase tracking-wide text-muted-foreground">
                    Open follow-ups
                  </p>
                  <p className="mt-2 font-heading text-3xl font-semibold tabular-nums text-primary">
                    {openFollowUps}
                  </p>
                  <p className="mt-1 text-ds-caption text-subtle">
                    Not completed (follow-ups queue is for admin / leader)
                  </p>
                </CardContent>
              </Card>
            )}
            <Link
              to="/dashboard/work/leads"
              className="block rounded-xl no-underline outline-none ring-offset-background transition hover:opacity-95 focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2"
            >
              <Card className="h-full border-primary/20 transition-colors hover:border-primary/35">
                <CardContent className="pt-6">
                  <p className="text-ds-caption font-medium uppercase tracking-wide text-muted-foreground">
                    Won
                  </p>
                  <p className="mt-2 font-heading text-3xl font-semibold tabular-nums text-success">
                    {metrics.won}
                  </p>
                  <p className="mt-1 text-ds-caption text-subtle">
                    {metrics.winRatePct !== null
                      ? `Win rate ${metrics.winRatePct}% (won / won+lost) — open leads`
                      : 'No closed outcomes yet — open leads'}
                  </p>
                </CardContent>
              </Card>
            </Link>
            <Link
              to="/dashboard/work/leads"
              className="block rounded-xl no-underline outline-none ring-offset-background transition hover:opacity-95 focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2"
            >
              <Card className="h-full border-primary/20 transition-colors hover:border-primary/35">
                <CardContent className="pt-6">
                  <p className="text-ds-caption font-medium uppercase tracking-wide text-muted-foreground">
                    New leads
                  </p>
                  <p className="mt-2 font-heading text-3xl font-semibold tabular-nums text-foreground">
                    {metrics.newLeads}
                  </p>
                  <p className="mt-1 text-ds-caption text-subtle">
                    In &quot;new&quot; stage — open list
                  </p>
                </CardContent>
              </Card>
            </Link>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="border-primary/20 lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-ds-h3">Pipeline by stage</CardTitle>
            <CardDescription>
              Counts from workboard (same rules as your lead visibility)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {wb.isPending && sessionReady ? (
              <LoadingState label="Loading pipeline…" />
            ) : (
              <>
                <div className="flex h-44 items-end justify-between gap-1.5 border-b border-border/60 px-0.5 pb-0 sm:gap-2">
                  {metrics.bars.map((b) => {
                    const h = Math.round((b.total / metrics.chartMax) * 100)
                    return (
                      <div
                        key={b.status}
                        className="flex min-w-0 flex-1 flex-col items-center gap-2"
                      >
                        <span className="text-center text-ds-caption font-medium tabular-nums text-foreground">
                          {b.total}
                        </span>
                        <div
                          className="w-full max-w-[3rem] rounded-t-md bg-gradient-to-t from-primary/85 to-primary/35"
                          style={{ height: `${Math.max(h, 4)}%` }}
                          title={`${b.label}: ${b.total}`}
                        />
                        <span className="line-clamp-2 text-center text-[0.65rem] leading-tight text-subtle">
                          {b.label}
                        </span>
                      </div>
                    )
                  })}
                </div>
                {metrics.bars.length === 0 ? (
                  <p className="mt-4 text-center text-ds-body text-muted-foreground">
                    No pipeline data yet — add leads from Work or Leads.
                  </p>
                ) : null}
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-primary/20 lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-ds-h3">Quick actions</CardTitle>
            <CardDescription>Jump to common screens</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {quickActions.map((action) => {
              const Icon = action.Icon
              return (
                <Button
                  key={action.path}
                  variant="outline"
                  className="h-auto w-full p-0 font-normal"
                  asChild
                >
                  <Link
                    to={action.to}
                    className="inline-flex w-full items-center justify-between gap-3 px-4 py-3 no-underline"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <Icon className="size-4 shrink-0 text-primary" aria-hidden />
                      <span className="truncate font-medium text-foreground">{action.label}</span>
                      {action.badgeCount != null ? (
                        <Badge variant="primary" className="ml-1 shrink-0">
                          {action.badgeCount}
                        </Badge>
                      ) : null}
                    </span>
                    <ArrowRight className="size-4 shrink-0 opacity-60" aria-hidden />
                  </Link>
                </Button>
              )
            })}
          </CardContent>
        </Card>
      </div>

      <Card className="border-primary/20">
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-ds-h3">Recent leads</CardTitle>
            <CardDescription>
              Newest leads loaded in the workboard snapshot (up to 8)
            </CardDescription>
          </div>
          <Button variant="secondary" size="sm" asChild>
            <Link to="/dashboard/work/leads">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {wb.isPending && sessionReady ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : recentLeads.length === 0 ? (
            <p className="text-ds-body text-muted-foreground">
              No leads in the current workboard window yet. Open{' '}
              <Link
                to="/dashboard/work/leads"
                className="font-medium text-primary underline-offset-2 hover:underline"
              >
                Leads
              </Link>{' '}
              to create or import.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead className="text-right">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentLeads.map((lead) => (
                  <TableRow key={lead.id}>
                    <TableCell className="font-medium">{lead.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{statusLabel(lead.status)}</Badge>
                    </TableCell>
                    <TableCell className="text-right text-ds-caption text-muted-foreground">
                      {new Date(lead.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <p className="text-center text-ds-caption text-subtle">
        {meta
          ? `${meta.name} · API v${meta.api_version}`
          : 'Loading server meta…'}
      </p>

      {mePending && !me ? (
        <div className="flex justify-center py-8">
          <LoadingState label="Loading session…" />
        </div>
      ) : null}
    </div>
  )
}
