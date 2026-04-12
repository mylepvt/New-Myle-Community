import { NavLink } from 'react-router-dom'
import { MoreHorizontal } from 'lucide-react'

import { getDashboardNavIcon } from '@/config/dashboard-nav-icons'
import {
  DASHBOARD_ROUTE_DEFS,
  type ClientNavFlags,
  type DashboardRouteDef,
  resolveTitleForPath,
  routeDefAccessible,
} from '@/config/dashboard-registry'
import { cn } from '@/lib/utils'
import type { Role } from '@/types/role'

const TAB_ORDER = ['', 'work/leads', 'work/workboard'] as const

/** Short labels for tab bar (iOS-style compact). */
const SHORT_LABEL: Record<string, string> = {
  '': 'Home',
  'work/leads': 'Leads',
  'work/workboard': 'Board',
  'work/follow-ups': 'Tasks',
  intelligence: 'Intel',
}

type Props = {
  role: Role
  flags: ClientNavFlags
  /** Legacy-style gate: only Training until completed */
  trainingLocked?: boolean
  onOpenMenu: () => void
}

function defForPath(path: string) {
  return DASHBOARD_ROUTE_DEFS.find((d) => d.path === path)
}

function fourthTabDef(
  role: Role,
  flags: ClientNavFlags,
): DashboardRouteDef | undefined {
  const intel = defForPath('intelligence')
  if (intel && routeDefAccessible(intel, role, flags)) return intel
  const followUps = defForPath('work/follow-ups')
  if (followUps && routeDefAccessible(followUps, role, flags)) return followUps
  return undefined
}

export function DashboardMobileTabBar({
  role,
  flags,
  trainingLocked = false,
  onOpenMenu,
}: Props) {
  if (trainingLocked) {
    const def = defForPath('system/training')
    if (!def || !routeDefAccessible(def, role, flags)) return null
    const Icon = getDashboardNavIcon('system/training')
    const label =
      resolveTitleForPath('system/training', role) ?? def.label
    return (
      <nav
        className="fixed bottom-0 left-0 right-0 z-30 border-t border-border/80 bg-background/85 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70 md:hidden"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
        role="navigation"
        aria-label="Training"
      >
        <div className="mx-auto flex max-w-lg items-stretch justify-around gap-0 px-1 pt-1">
          <NavLink
            to="/dashboard/system/training"
            className={({ isActive }) =>
              cn(
                'flex min-h-[48px] min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-[0.65rem] font-medium leading-none transition-colors active:opacity-70',
                isActive ? 'text-primary' : 'text-muted-foreground',
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  className={cn(
                    'size-[22px] shrink-0',
                    isActive ? 'text-primary' : 'text-muted-foreground',
                  )}
                  strokeWidth={isActive ? 2.25 : 1.75}
                  aria-hidden
                />
                <span className="truncate">{label}</span>
              </>
            )}
          </NavLink>
          <button
            type="button"
            onClick={onOpenMenu}
            className="flex min-h-[48px] min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-[0.65rem] font-medium leading-none text-muted-foreground transition-colors active:opacity-70"
            aria-label="Open menu"
          >
            <MoreHorizontal className="size-[22px] shrink-0" strokeWidth={1.75} aria-hidden />
            <span className="truncate">Menu</span>
          </button>
        </div>
      </nav>
    )
  }

  const fourth = fourthTabDef(role, flags)
  const defs: DashboardRouteDef[] = [
    ...TAB_ORDER.map((p) => defForPath(p)).filter(
      (d): d is DashboardRouteDef => d != null,
    ),
    fourth,
  ].filter((d): d is DashboardRouteDef => d != null && routeDefAccessible(d, role, flags))

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-30 border-t border-border/80 bg-background/85 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70 md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      role="navigation"
      aria-label="Main tabs"
    >
      <div className="mx-auto flex max-w-lg items-stretch justify-around gap-0 px-1 pt-1">
        {defs.map((def) => {
          const to = def.path === '' ? '/dashboard' : `/dashboard/${def.path}`
          const Icon = getDashboardNavIcon(def.path)
          const label =
            SHORT_LABEL[def.path] ??
            resolveTitleForPath(def.path, role) ??
            def.label
          return (
            <NavLink
              key={def.path || 'home'}
              to={to}
              end={def.end ?? false}
              className={({ isActive }) =>
                cn(
                  'flex min-h-[48px] min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-[0.65rem] font-medium leading-none transition-colors active:opacity-70',
                  isActive
                    ? 'text-primary'
                    : 'text-muted-foreground',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={cn(
                      'size-[22px] shrink-0',
                      isActive ? 'text-primary' : 'text-muted-foreground',
                    )}
                    strokeWidth={isActive ? 2.25 : 1.75}
                    aria-hidden
                  />
                  <span className="truncate">{label}</span>
                </>
              )}
            </NavLink>
          )
        })}

        <button
          type="button"
          onClick={onOpenMenu}
          className="flex min-h-[48px] min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-[0.65rem] font-medium leading-none text-muted-foreground transition-colors active:opacity-70"
          aria-label="Open full menu"
        >
          <MoreHorizontal className="size-[22px] shrink-0" strokeWidth={1.75} aria-hidden />
          <span className="truncate">More</span>
        </button>
      </div>
    </nav>
  )
}
