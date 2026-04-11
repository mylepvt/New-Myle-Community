import { type FormEvent, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Bell, Home, LogOut, Menu, PanelLeftClose, Search } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { DashboardOutletErrorBoundary } from '@/components/routing/DashboardOutletErrorBoundary'
import { getDashboardNavIcon } from '@/config/dashboard-nav-icons'
import { filterDashboardNav, resolveItemLabel } from '@/config/dashboard-nav'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { useDashboardShellRole } from '@/hooks/use-dashboard-shell-role'
import { useMetaQuery } from '@/hooks/use-meta-query'
import { useRealtimeInvalidation } from '@/hooks/use-realtime-invalidation'
import { useSyncRoleFromMe } from '@/hooks/use-sync-role-from-me'
import { cn } from '@/lib/utils'
import { authLogout } from '@/lib/auth-api'
import { useAuthStore } from '@/stores/auth-store'
import { useShellStore } from '@/stores/shell-store'
import { roleShortLabel } from '@/types/role'

export function DashboardLayout() {
  useSyncRoleFromMe()
  useRealtimeInvalidation(true)
  const { data: meta } = useMetaQuery()
  const { data: me } = useAuthMeQuery()
  const { role: shellRole, isPending: rolePending } = useDashboardShellRole()
  const navigate = useNavigate()
  const { sidebarOpen, toggleSidebar } = useShellStore()
  const logout = useAuthStore((s) => s.logout)
  const [headerSearch, setHeaderSearch] = useState('')

  function submitHeaderSearch(e: FormEvent) {
    e.preventDefault()
    const q = headerSearch.trim()
    if (q) {
      navigate(`/dashboard/work/leads?q=${encodeURIComponent(q)}`)
    } else {
      navigate('/dashboard/work/leads')
    }
  }

  const navFlags = {
    intelligence: meta?.features.intelligence ?? true,
  }
  const sections =
    shellRole != null ? filterDashboardNav(shellRole, navFlags) : []
  const envLabel = meta?.environment

  const displayInitial =
    me?.email?.[0]?.toUpperCase() ??
    me?.role?.[0]?.toUpperCase() ??
    shellRole?.[0]?.toUpperCase() ??
    '?'

  async function handleLogout() {
    try {
      await authLogout()
    } catch {
      /* still clear local session */
    }
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-dvh bg-background">
      <aside
        className={cn(
          'flex min-h-dvh shrink-0 flex-col border-r border-white/[0.06] bg-surface shadow-sidebar-glow transition-[width] duration-300 ease-out',
          sidebarOpen ? 'w-[17rem]' : 'w-0 overflow-hidden border-0',
        )}
      >
        <div className="flex h-16 shrink-0 items-center border-b border-white/[0.06] px-4">
          <Link
            to="/dashboard"
            className="font-heading text-lg font-semibold tracking-tight text-foreground"
          >
            Myle
          </Link>
          {envLabel && envLabel !== 'production' ? (
            <span
              className="ml-2 shrink-0 rounded border border-warning/40 bg-warning/10 px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-warning"
              title="Server-reported environment (APP_ENV)"
            >
              {envLabel}
            </span>
          ) : null}
        </div>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto overflow-x-hidden px-2 py-3 pb-2">
          {rolePending && shellRole == null ? (
            <div className="space-y-2 px-2" aria-busy="true" aria-label="Loading navigation">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 animate-pulse rounded-2xl bg-muted/50"
                />
              ))}
            </div>
          ) : null}
          {shellRole != null
            ? sections.map((section) => (
            <div key={section.id}>
              {section.label ? (
                <p className="mb-2 px-3 text-[0.62rem] font-semibold uppercase tracking-label-wide text-muted-foreground/80">
                  {section.label}
                </p>
              ) : null}
              <ul className="flex flex-col gap-1">
                {section.items.map((item) => {
                  const to =
                    item.path === '' ? '/dashboard' : `/dashboard/${item.path}`
                  const label = resolveItemLabel(item, shellRole)
                  const Icon = getDashboardNavIcon(item.path)
                  return (
                    <li key={item.path || 'index'}>
                      <NavLink
                        to={to}
                        end={item.end ?? false}
                        className={({ isActive }) =>
                          cn(
                            'group relative flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all duration-200',
                            isActive
                              ? 'bg-primary font-semibold text-primary-foreground shadow-md shadow-primary/25'
                              : 'border border-transparent text-muted-foreground hover:bg-white/[0.06] hover:text-foreground',
                          )
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <Icon
                              className={cn(
                                'size-[1.125rem] shrink-0',
                                isActive ? 'text-primary-foreground' : 'opacity-80',
                              )}
                              aria-hidden
                            />
                            <span className="min-w-0 flex-1 truncate">
                              {label}
                            </span>
                          </>
                        )}
                      </NavLink>
                    </li>
                  )
                })}
              </ul>
            </div>
              ))
            : null}
        </nav>

        <div className="mt-auto shrink-0 border-t border-border/80 p-3">
          <Button
            type="button"
            variant="outline"
            className="w-full gap-2 border-destructive/45 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={() => void handleLogout()}
          >
            <LogOut className="size-4" aria-hidden />
            Log out
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-white/[0.06] bg-background/95 px-3 shadow-header-bar backdrop-blur-xl">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? <PanelLeftClose /> : <Menu />}
          </Button>

          <form
            className="relative mx-auto hidden max-w-xl flex-1 sm:block"
            onSubmit={submitHeaderSearch}
            role="search"
          >
            <Search
              className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <input
              type="search"
              name="q"
              value={headerSearch}
              onChange={(e) => setHeaderSearch(e.target.value)}
              placeholder="Search leads (Enter → open list)"
              className="h-10 w-full rounded-full border border-white/[0.08] bg-muted/40 pl-10 pr-4 text-ds-body text-foreground placeholder:text-muted-foreground shadow-glass-inset focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/25"
              aria-label="Search leads"
              autoComplete="off"
            />
          </form>

          <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:flex-initial sm:gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="relative hidden text-muted-foreground hover:text-foreground sm:inline-flex"
              aria-label="Notifications"
            >
              <Bell className="size-5" />
              <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-primary ring-2 ring-background shadow-[0_0_8px_hsl(68_100%_50%/0.8)]" />
            </Button>

            {shellRole != null ? (
              <span
                className="max-w-[7rem] truncate rounded-xl border border-white/[0.08] bg-muted/40 px-2.5 py-1.5 text-center text-ds-caption font-semibold text-foreground shadow-glass-inset sm:max-w-[9rem]"
                title="Your role from the signed-in account"
              >
                {roleShortLabel(shellRole)}
              </span>
            ) : rolePending ? (
              <span className="inline-block h-8 w-16 animate-pulse rounded-lg bg-muted/50" />
            ) : null}

            <div
              className="flex size-9 shrink-0 items-center justify-center rounded-full border border-primary/35 bg-primary/15 text-xs font-bold text-primary"
              title={me?.email ?? shellRole ?? ''}
            >
              {displayInitial}
            </div>

            <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex">
              <Link to="/" className="gap-1.5 text-muted-foreground">
                <Home className="size-4" />
                Home
              </Link>
            </Button>
          </div>
        </header>

        <main className="relative flex-1 overflow-auto bg-gradient-to-b from-background via-background to-muted/25 p-4 md:p-6 lg:p-8">
          <DashboardOutletErrorBoundary>
            <Outlet />
          </DashboardOutletErrorBoundary>
        </main>
      </div>
    </div>
  )
}
