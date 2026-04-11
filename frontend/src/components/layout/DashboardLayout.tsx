import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Bell, Home, LogOut, Menu, PanelLeftClose, Search } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { DashboardOutletErrorBoundary } from '@/components/routing/DashboardOutletErrorBoundary'
import { getDashboardNavIcon } from '@/config/dashboard-nav-icons'
import { filterDashboardNav, resolveItemLabel } from '@/config/dashboard-nav'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { useMetaQuery } from '@/hooks/use-meta-query'
import { useRealtimeInvalidation } from '@/hooks/use-realtime-invalidation'
import { useSyncRoleFromMe } from '@/hooks/use-sync-role-from-me'
import { cn } from '@/lib/utils'
import { authLogout } from '@/lib/auth-api'
import { useAuthStore } from '@/stores/auth-store'
import { useRoleStore } from '@/stores/role-store'
import { useShellStore } from '@/stores/shell-store'
import { ROLES, type Role } from '@/types/role'

export function DashboardLayout() {
  useSyncRoleFromMe()
  useRealtimeInvalidation(true)
  const { data: meta } = useMetaQuery()
  const { data: me } = useAuthMeQuery()
  const navigate = useNavigate()
  const { sidebarOpen, toggleSidebar } = useShellStore()
  const role = useRoleStore((s) => s.role)
  const setRole = useRoleStore((s) => s.setRole)
  const logout = useAuthStore((s) => s.logout)

  const navFlags = {
    intelligence: meta?.features.intelligence ?? true,
  }
  const sections = filterDashboardNav(role, navFlags)
  const envLabel = meta?.environment

  const displayInitial =
    me?.email?.[0]?.toUpperCase() ??
    me?.role?.[0]?.toUpperCase() ??
    role[0]?.toUpperCase() ??
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
          'flex min-h-dvh shrink-0 flex-col border-r border-primary/15 bg-surface shadow-sidebar-glow transition-[width] duration-300 ease-out',
          sidebarOpen ? 'w-[17rem]' : 'w-0 overflow-hidden border-0',
        )}
      >
        <div className="flex h-16 shrink-0 items-center border-b border-primary/10 px-4">
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
          {sections.map((section) => (
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
                  const label = resolveItemLabel(item, role)
                  const Icon = getDashboardNavIcon(item.path)
                  return (
                    <li key={item.path || 'index'}>
                      <NavLink
                        to={to}
                        end={item.end ?? false}
                        className={({ isActive }) =>
                          cn(
                            'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200',
                            isActive
                              ? 'border border-primary/45 bg-primary/[0.09] font-semibold text-primary shadow-glass-glow'
                              : 'border border-transparent text-muted-foreground hover:border-border hover:bg-muted/40 hover:text-foreground',
                          )
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <Icon
                              className={cn(
                                'size-[1.125rem] shrink-0',
                                isActive ? 'text-primary' : 'opacity-80',
                              )}
                              aria-hidden
                            />
                            <span className="min-w-0 flex-1 truncate">
                              {label}
                            </span>
                            {isActive ? (
                              <span
                                className="size-2 shrink-0 rounded-full bg-primary shadow-[0_0_10px_hsl(var(--primary)/0.9)]"
                                aria-hidden
                              />
                            ) : null}
                          </>
                        )}
                      </NavLink>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
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
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-primary/10 bg-background/90 px-3 shadow-header-bar backdrop-blur-xl">
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

          <div className="relative mx-auto hidden max-w-xl flex-1 sm:block">
            <Search
              className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <input
              type="search"
              placeholder="Search leads, members, reports…"
              className="h-10 w-full rounded-full border border-border bg-muted/50 pl-10 pr-4 text-ds-body text-foreground placeholder:text-muted-foreground shadow-glass-inset focus:border-primary/45 focus:outline-none focus:ring-2 focus:ring-primary/20"
              aria-label="Search"
            />
          </div>

          <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:flex-initial sm:gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="relative hidden text-muted-foreground hover:text-foreground sm:inline-flex"
              aria-label="Notifications"
            >
              <Bell className="size-5" />
              <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-primary ring-2 ring-background" />
            </Button>

            <label className="sr-only" htmlFor="role-preview">
              Preview as role
            </label>
            <select
              id="role-preview"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="max-w-[6.5rem] rounded-lg border border-border bg-muted/60 px-2 py-1.5 text-ds-caption font-medium text-foreground shadow-glass-inset focus:outline-none focus:ring-2 focus:ring-primary/25 sm:max-w-[9rem]"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>

            <div
              className="flex size-9 shrink-0 items-center justify-center rounded-full border border-primary/25 bg-primary/10 text-xs font-bold text-primary"
              title={me?.email ?? role}
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

        <main className="relative flex-1 overflow-auto bg-gradient-to-b from-background via-background to-muted/20 p-4 md:p-6 lg:p-8">
          <DashboardOutletErrorBoundary>
            <Outlet />
          </DashboardOutletErrorBoundary>
        </main>
      </div>
    </div>
  )
}
