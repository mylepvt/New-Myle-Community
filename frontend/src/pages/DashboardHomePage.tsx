import { TrendingUp } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { t } from '@/lib/i18n'
import { useRoleStore } from '@/stores/role-store'
import type { Role } from '@/types/role'

const titles: Record<Role, string> = {
  admin: 'Admin overview',
  leader: 'Leader overview',
  team: 'Your workspace',
}

const kpis = [
  { label: 'Total leads', value: '400+', hint: 'In pipeline', tone: 'text-success' },
  { label: 'Reachable', value: '250', hint: 'Contactable', tone: 'text-foreground' },
  { label: 'Follow-ups due', value: '24', hint: 'This week', tone: 'text-foreground' },
  { label: 'Win rate', value: '32%', hint: 'Last 30d', tone: 'text-primary' },
] as const

export function DashboardHomePage() {
  const role = useRoleStore((s) => s.role)
  const { data: me } = useAuthMeQuery()
  const firstName =
    me?.email?.split('@')[0]?.split(/[._-]/)[0] ?? 'there'

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Card className="overflow-hidden border-primary/25 bg-gradient-to-br from-card via-card to-primary/[0.06]">
        <CardHeader className="flex flex-row items-start justify-between gap-4 pb-2">
          <div>
            <CardDescription>Today</CardDescription>
            <CardTitle className="mt-1 font-heading text-ds-h1 capitalize tracking-tight">
              Welcome, {firstName}!
            </CardTitle>
            <p className="mt-2 max-w-xl text-ds-body text-muted-foreground">
              {titles[role]} — {t('appTagline')}
            </p>
          </div>
          <div className="hidden shrink-0 rounded-2xl border border-primary/20 bg-primary/10 p-3 text-primary sm:block">
            <TrendingUp className="size-10" strokeWidth={1.25} aria-hidden />
          </div>
        </CardHeader>
      </Card>

      <div>
        <h2 className="mb-3 font-heading text-ds-h2 text-foreground">Overview</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.map((k) => (
            <Card key={k.label} className="border-primary/20">
              <CardContent className="pt-6">
                <p className="text-ds-caption font-medium uppercase tracking-wide text-muted-foreground">
                  {k.label}
                </p>
                <p className={`mt-2 font-heading text-3xl font-semibold tabular-nums ${k.tone}`}>
                  {k.value}
                </p>
                <p className="mt-1 text-ds-caption text-subtle">{k.hint}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="border-primary/20 lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-ds-h3">Activity</CardTitle>
            <CardDescription>Last 7 days (sample)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-40 items-end justify-between gap-2 border-b border-border/60 px-1 pb-0">
              {[40, 65, 45, 80, 55, 90, 70].map((h, i) => (
                <div
                  key={i}
                  className="w-full max-w-[2.5rem] rounded-t-md bg-gradient-to-t from-primary/80 to-primary/40"
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
            <div className="mt-2 flex justify-between text-ds-caption text-subtle">
              <span>Mon</span>
              <span>Sun</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-primary/20 lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-ds-h3">Quick actions</CardTitle>
            <CardDescription>Shortcuts for your role</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-ds-body text-muted-foreground">
            <p>Open leads from the sidebar to manage your pipeline.</p>
            <p>Use the search bar to find records faster (UI preview).</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
