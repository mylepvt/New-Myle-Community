import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LogOut, Menu, PanelLeftClose } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { DashboardOutletErrorBoundary } from '@/components/routing/DashboardOutletErrorBoundary'
import { filterDashboardNav, resolveItemLabel } from '@/config/dashboard-nav'
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
    <div className="flex min-h-dvh">
      <aside
        className={cn(
          'flex flex-col border-r border-white/[0.1] bg-white/[0.04] shadow-sidebar-glow backdrop-blur-2xl backdrop-saturate-150 transition-[width] duration-300 ease-out',
          sidebarOpen ? 'w-60 shrink-0' : 'w-0 shrink-0 overflow-hidden border-0',
        )}
      >
        <div className="flex h-14 shrink-0 items-center border-b border-white/[0.08] bg-white/[0.03] px-3 shadow-header-bar backdrop-blur-md">
          <div className="flex min-w-0 items-center gap-2">
            <Link
              to="/dashboard"
              className="truncate bg-gradient-to-r from-foreground via-foreground to-primary/75 bg-clip-text text-sm font-semibold tracking-tight text-transparent"
            >
              Myle vl2
            </Link>
            {envLabel && envLabel !== 'production' ? (
              <span
                className="shrink-0 rounded border border-amber-500/35 bg-amber-500/10 px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-amber-200/90"
                title="Server-reported environment (APP_ENV)"
              >
                {envLabel}
              </span>
            ) : null}
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-4 overflow-y-auto overflow-x-hidden p-2 pb-4">
          {sections.map((section) => (
            <div key={section.id}>
              {section.label ? (
                <p className="mb-1.5 px-2 text-[0.62rem] font-semibold uppercase tracking-label-wide text-muted-foreground/75">
                  {section.label}
                </p>
              ) : null}
              <ul className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const to =
                    item.path === '' ? '/dashboard' : `/dashboard/${item.path}`
                  const label = resolveItemLabel(item, role)
                  return (
                    <li key={item.path || 'index'}>
                      <NavLink
                        to={to}
                        end={item.end ?? false}
                        className={({ isActive }) =>
                          cn(
                            'relative block rounded-lg py-2.5 pl-3 pr-3 text-sm transition-all duration-200',
                            isActive
                              ? 'bg-gradient-to-r from-primary/18 to-primary/[0.06] font-medium text-primary shadow-glass-glow before:absolute before:inset-y-1 before:left-0 before:w-[3px] before:rounded-full before:bg-primary before:shadow-[0_0_14px_hsl(var(--primary)/0.55)]'
                              : 'text-muted-foreground hover:bg-white/[0.05] hover:text-foreground',
                          )
                        }
                      >
                        {label}
                      </NavLink>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-white/[0.1] bg-white/[0.04] px-3 shadow-header-bar backdrop-blur-2xl backdrop-saturate-150">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? <PanelLeftClose /> : <Menu />}
          </Button>

          <div className="flex min-w-0 flex-1 justify-end sm:justify-start">
            <label className="sr-only" htmlFor="role-preview">
              Preview as role
            </label>
            <select
              id="role-preview"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="max-w-[9rem] rounded-lg border border-white/[0.12] bg-white/[0.06] px-2.5 py-1.5 text-xs font-medium text-foreground shadow-glass-inset backdrop-blur-sm focus:outline-none focus:ring-2 focus:ring-primary/35"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/" className="text-muted-foreground">
                Home
              </Link>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => void handleLogout()}
              aria-label="Sign out"
            >
              <LogOut className="size-4" />
            </Button>
          </div>
        </header>

        <main className="relative flex-1 overflow-auto bg-gradient-to-b from-transparent via-transparent to-background/40 p-4 md:p-6 lg:p-8">
          <DashboardOutletErrorBoundary>
            <Outlet />
          </DashboardOutletErrorBoundary>
        </main>
      </div>
    </div>
  )
}
