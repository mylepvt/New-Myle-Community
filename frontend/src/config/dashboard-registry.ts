/**
 * Single source of truth for dashboard IA: nav labels + how each path renders.
 * **Route ↔ role mapping** lives only in `dashboard-route-roles.json` (this folder) — imported as `routeRoles(path)`.
 * Kept under `frontend/src/config/` so Docker/CI builds that only copy `frontend/` still resolve the file.
 * `dashboard-nav.ts` and routing consume this — do not duplicate path lists elsewhere.
 */
import routeRolesData from './dashboard-route-roles.json'
import { isRole, type Role } from '@/types/role'

const ROUTE_ROLES = validateRouteRolesMap(routeRolesData as Record<string, string[]>)

function validateRouteRolesMap(raw: Record<string, string[]>): Record<string, Role[]> {
  const out: Record<string, Role[]> = {}
  for (const [path, roles] of Object.entries(raw)) {
    const rr: Role[] = []
    for (const x of roles) {
      if (!isRole(x)) {
        throw new Error(
          `dashboard-route-roles.json: invalid role "${x}" for path "${path}"`,
        )
      }
      rr.push(x)
    }
    out[path] = rr
  }
  return out
}

/** Which roles may open this dashboard path — from `./dashboard-route-roles.json` only. */
function routeRoles(path: string): Role[] {
  const r = ROUTE_ROLES[path]
  if (!r) {
    throw new Error(`dashboard-route-roles.json: missing entry for path "${path}"`)
  }
  return r
}

export type ClientNavFlags = {
  intelligence: boolean
}

/** Legacy nav item shape (sidebar). */
export type DashboardNavItem = {
  path: string
  label: string
  roles: Role[]
  end?: boolean
  labelByRole?: Partial<Record<Role, string>>
  requiresIntelligence?: boolean
}

export type DashboardNavSection = {
  id: string
  label: string
  items: DashboardNavItem[]
}

/** What to render for “full” product surfaces (non-stub). */
export type FullUiSurface =
  | { kind: 'leads'; listMode: 'active' | 'archived' }
  | { kind: 'workboard' }
  | { kind: 'follow-ups' }
  | { kind: 'retarget' }
  | { kind: 'lead-flow' }
  | { kind: 'lead-pool' }
  | { kind: 'recycle-bin' }
  | { kind: 'intelligence' }
  | { kind: 'team-members' }
  | { kind: 'my-team' }
  | { kind: 'enrollment-approvals' }
  | {
      kind: 'system'
      surface: 'training' | 'decision-engine' | 'coaching'
    }
  | {
      kind: 'analytics'
      surface: 'activity-log' | 'day-2-report'
    }
  | { kind: 'wallet' }
  | { kind: 'finance-recharges' }

export type DashboardRouteDef = {
  path: string
  section: { id: string; label: string }
  label: string
  roles: Role[]
  end?: boolean
  labelByRole?: Partial<Record<Role, string>>
  requiresIntelligence?: boolean
} & (
  | { surface: 'dashboard-home' }
  | { surface: 'full'; ui: FullUiSurface }
  | { surface: 'stub'; stubApiPath: string }
  | { surface: 'placeholder' }
)

const SECTION_ORDER: { id: string; label: string }[] = [
  { id: 'main', label: '' },
  { id: 'execution', label: 'Execution' },
  { id: 'work', label: 'Work' },
  { id: 'team', label: 'Team' },
  { id: 'system', label: 'System' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'finance', label: 'Finance' },
  { id: 'other', label: 'Other' },
  { id: 'settings', label: 'Settings' },
]

/**
 * Ordered list — same order as previous `dashboard-nav.ts` sections/items.
 */
export const DASHBOARD_ROUTE_DEFS: DashboardRouteDef[] = [
  {
    path: '',
    section: { id: 'main', label: '' },
    label: 'Dashboard',
    roles: routeRoles(''),
    end: true,
    surface: 'dashboard-home',
  },
  {
    path: 'execution/at-risk-leads',
    section: { id: 'execution', label: 'Execution' },
    label: 'At-risk leads',
    roles: routeRoles('execution/at-risk-leads'),
    surface: 'stub',
    stubApiPath: '/api/v1/execution/at-risk-leads',
  },
  {
    path: 'execution/lead-ledger',
    section: { id: 'execution', label: 'Execution' },
    label: 'Lead ledger',
    roles: routeRoles('execution/lead-ledger'),
    surface: 'stub',
    stubApiPath: '/api/v1/execution/lead-ledger',
  },
  {
    path: 'work/leads',
    section: { id: 'work', label: 'Work' },
    label: 'My Leads',
    labelByRole: { admin: 'All Leads' },
    roles: routeRoles('work/leads'),
    surface: 'full',
    ui: { kind: 'leads', listMode: 'active' },
  },
  {
    path: 'work/workboard',
    section: { id: 'work', label: 'Work' },
    label: 'Workboard',
    roles: routeRoles('work/workboard'),
    surface: 'full',
    ui: { kind: 'workboard' },
  },
  {
    path: 'work/follow-ups',
    section: { id: 'work', label: 'Work' },
    label: 'Follow-ups',
    roles: routeRoles('work/follow-ups'),
    surface: 'full',
    ui: { kind: 'follow-ups' },
  },
  {
    path: 'work/retarget',
    section: { id: 'work', label: 'Work' },
    label: 'Retarget',
    roles: routeRoles('work/retarget'),
    surface: 'full',
    ui: { kind: 'retarget' },
  },
  {
    path: 'work/lead-flow',
    section: { id: 'work', label: 'Work' },
    label: 'Lead flow',
    roles: routeRoles('work/lead-flow'),
    surface: 'full',
    ui: { kind: 'lead-flow' },
  },
  {
    path: 'work/archived',
    section: { id: 'work', label: 'Work' },
    label: 'Archived leads',
    roles: routeRoles('work/archived'),
    surface: 'full',
    ui: { kind: 'leads', listMode: 'archived' },
  },
  {
    path: 'work/add-lead',
    section: { id: 'work', label: 'Work' },
    label: 'Add lead',
    roles: routeRoles('work/add-lead'),
    surface: 'full',
    ui: { kind: 'leads', listMode: 'active' },
  },
  {
    path: 'work/lead-pool',
    section: { id: 'work', label: 'Work' },
    label: 'Lead pool',
    roles: routeRoles('work/lead-pool'),
    surface: 'full',
    ui: { kind: 'lead-pool' },
  },
  {
    path: 'work/lead-pool-admin',
    section: { id: 'work', label: 'Work' },
    label: 'Admin lead pool',
    roles: routeRoles('work/lead-pool-admin'),
    surface: 'full',
    ui: { kind: 'lead-pool' },
  },
  {
    path: 'work/recycle-bin',
    section: { id: 'work', label: 'Work' },
    label: 'Recycle bin',
    roles: routeRoles('work/recycle-bin'),
    surface: 'full',
    ui: { kind: 'recycle-bin' },
  },
  {
    path: 'intelligence',
    section: { id: 'work', label: 'Work' },
    label: 'Intelligence',
    roles: routeRoles('intelligence'),
    requiresIntelligence: true,
    surface: 'full',
    ui: { kind: 'intelligence' },
  },
  {
    path: 'team/members',
    section: { id: 'team', label: 'Team' },
    label: 'Members',
    roles: routeRoles('team/members'),
    surface: 'full',
    ui: { kind: 'team-members' },
  },
  {
    path: 'team/reports',
    section: { id: 'team', label: 'Team' },
    label: 'Reports',
    roles: routeRoles('team/reports'),
    surface: 'stub',
    stubApiPath: '/api/v1/team/reports',
  },
  {
    path: 'team/approvals',
    section: { id: 'team', label: 'Team' },
    label: 'Approvals',
    roles: routeRoles('team/approvals'),
    surface: 'stub',
    stubApiPath: '/api/v1/team/approvals',
  },
  {
    path: 'team/enrollment-approvals',
    section: { id: 'team', label: 'Team' },
    label: 'Enrollment approvals (INR 196)',
    roles: routeRoles('team/enrollment-approvals'),
    surface: 'full',
    ui: { kind: 'enrollment-approvals' },
  },
  {
    path: 'team/my-team',
    section: { id: 'team', label: 'Team' },
    label: 'My team',
    roles: routeRoles('team/my-team'),
    surface: 'full',
    ui: { kind: 'my-team' },
  },
  {
    path: 'system/training',
    section: { id: 'system', label: 'System' },
    label: 'Training (admin)',
    roles: routeRoles('system/training'),
    surface: 'full',
    ui: { kind: 'system', surface: 'training' },
  },
  {
    path: 'system/decision-engine',
    section: { id: 'system', label: 'System' },
    label: 'Decision engine',
    roles: routeRoles('system/decision-engine'),
    surface: 'full',
    ui: { kind: 'system', surface: 'decision-engine' },
  },
  {
    path: 'system/coaching',
    section: { id: 'system', label: 'System' },
    label: 'Coaching panel',
    roles: routeRoles('system/coaching'),
    surface: 'full',
    ui: { kind: 'system', surface: 'coaching' },
  },
  {
    path: 'analytics/activity-log',
    section: { id: 'analytics', label: 'Analytics' },
    label: 'Activity log',
    roles: routeRoles('analytics/activity-log'),
    surface: 'full',
    ui: { kind: 'analytics', surface: 'activity-log' },
  },
  {
    path: 'analytics/day-2-report',
    section: { id: 'analytics', label: 'Analytics' },
    label: 'Day 2 test report',
    roles: routeRoles('analytics/day-2-report'),
    surface: 'full',
    ui: { kind: 'analytics', surface: 'day-2-report' },
  },
  {
    path: 'finance/recharges',
    section: { id: 'finance', label: 'Finance' },
    label: 'Recharges',
    roles: routeRoles('finance/recharges'),
    surface: 'full',
    ui: { kind: 'finance-recharges' },
  },
  {
    path: 'finance/budget-export',
    section: { id: 'finance', label: 'Finance' },
    label: 'Budget export',
    roles: routeRoles('finance/budget-export'),
    surface: 'stub',
    stubApiPath: '/api/v1/finance/budget-export',
  },
  {
    path: 'finance/monthly-targets',
    section: { id: 'finance', label: 'Finance' },
    label: 'Monthly targets',
    roles: routeRoles('finance/monthly-targets'),
    surface: 'stub',
    stubApiPath: '/api/v1/finance/monthly-targets',
  },
  {
    path: 'finance/wallet',
    section: { id: 'finance', label: 'Finance' },
    label: 'My wallet',
    roles: routeRoles('finance/wallet'),
    surface: 'full',
    ui: { kind: 'wallet' },
  },
  {
    path: 'finance/lead-pool',
    section: { id: 'finance', label: 'Finance' },
    label: 'Lead pool',
    roles: routeRoles('finance/lead-pool'),
    surface: 'stub',
    stubApiPath: '/api/v1/finance/lead-pool',
  },
  {
    path: 'other/leaderboard',
    section: { id: 'other', label: 'Other' },
    label: 'Leaderboard',
    roles: routeRoles('other/leaderboard'),
    surface: 'stub',
    stubApiPath: '/api/v1/other/leaderboard',
  },
  {
    path: 'other/notice-board',
    section: { id: 'other', label: 'Other' },
    label: 'Notice board',
    roles: routeRoles('other/notice-board'),
    surface: 'stub',
    stubApiPath: '/api/v1/other/notice-board',
  },
  {
    path: 'other/live-session',
    section: { id: 'other', label: 'Other' },
    label: 'Live session',
    roles: routeRoles('other/live-session'),
    surface: 'stub',
    stubApiPath: '/api/v1/other/live-session',
  },
  {
    path: 'other/training',
    section: { id: 'other', label: 'Other' },
    label: 'My training',
    roles: routeRoles('other/training'),
    surface: 'stub',
    stubApiPath: '/api/v1/other/training',
  },
  {
    path: 'other/daily-report',
    section: { id: 'other', label: 'Other' },
    label: 'Daily report',
    roles: routeRoles('other/daily-report'),
    surface: 'stub',
    stubApiPath: '/api/v1/other/daily-report',
  },
  {
    path: 'settings/app',
    section: { id: 'settings', label: 'Settings' },
    label: 'General',
    roles: routeRoles('settings/app'),
    surface: 'stub',
    stubApiPath: '/api/v1/settings/app',
  },
  {
    path: 'settings/help',
    section: { id: 'settings', label: 'Settings' },
    label: 'Help',
    roles: routeRoles('settings/help'),
    surface: 'stub',
    stubApiPath: '/api/v1/settings/help',
  },
  {
    path: 'settings/all-members',
    section: { id: 'settings', label: 'Settings' },
    label: 'All members',
    roles: routeRoles('settings/all-members'),
    surface: 'stub',
    stubApiPath: '/api/v1/settings/all-members',
  },
  {
    path: 'settings/org-tree',
    section: { id: 'settings', label: 'Settings' },
    label: 'Org tree',
    roles: routeRoles('settings/org-tree'),
    surface: 'stub',
    stubApiPath: '/api/v1/settings/org-tree',
  },
]

function assertRouteRolesJsonMatchesDefs(
  defs: DashboardRouteDef[],
  map: Record<string, Role[]>,
): void {
  const paths = new Set(defs.map((d) => d.path))
  for (const k of Object.keys(map)) {
    if (!paths.has(k)) {
      throw new Error(
        `dashboard-route-roles.json: orphaned key "${k}" — not present in DASHBOARD_ROUTE_DEFS`,
      )
    }
  }
  for (const p of paths) {
    if (!Object.prototype.hasOwnProperty.call(map, p)) {
      throw new Error(
        `dashboard-route-roles.json: missing key for path "${p}" (every registry path needs a roles entry)`,
      )
    }
  }
}

assertRouteRolesJsonMatchesDefs(DASHBOARD_ROUTE_DEFS, ROUTE_ROLES)

function defToNavItem(def: DashboardRouteDef): DashboardNavItem {
  const base: DashboardNavItem = {
    path: def.path,
    label: def.label,
    roles: def.roles,
  }
  if (def.end !== undefined) base.end = def.end
  if (def.labelByRole) base.labelByRole = def.labelByRole
  if (def.requiresIntelligence !== undefined) {
    base.requiresIntelligence = def.requiresIntelligence
  }
  return base
}

/** Sidebar sections — one source of truth order. */
export function buildDashboardNavSections(): DashboardNavSection[] {
  return SECTION_ORDER.map((sec) => {
    const items = DASHBOARD_ROUTE_DEFS.filter(
      (d) => d.section.id === sec.id,
    ).map(defToNavItem)
    return { id: sec.id, label: sec.label, items }
  }).filter((s) => s.items.length > 0)
}

export const dashboardNavSections = buildDashboardNavSections()

export const dashboardChildPathSet = new Set(
  DASHBOARD_ROUTE_DEFS.map((d) => d.path).filter((p) => p.length > 0),
)

export function getDashboardChildRoute(
  path: string,
): DashboardRouteDef | undefined {
  return DASHBOARD_ROUTE_DEFS.find((d) => d.path === path && d.path !== '')
}

export function itemVisible(
  item: DashboardNavItem,
  role: Role,
  flags: ClientNavFlags,
): boolean {
  if (!item.roles.includes(role)) {
    return false
  }
  if (item.requiresIntelligence && !flags.intelligence) {
    return false
  }
  return true
}

export function filterDashboardNav(
  role: Role,
  flags: ClientNavFlags,
): DashboardNavSection[] {
  return dashboardNavSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => itemVisible(item, role, flags)),
    }))
    .filter((section) => section.items.length > 0)
}

export function resolveItemLabel(item: DashboardNavItem, role: Role): string {
  return item.labelByRole?.[role] ?? item.label
}

export function resolveTitleForPath(path: string, role: Role): string | undefined {
  const def = DASHBOARD_ROUTE_DEFS.find((d) => d.path === path)
  if (!def) return undefined
  return def.labelByRole?.[role] ?? def.label
}

/** Stub GET paths for `ShellStubPage` — derived from registry (no second list). */
export const SHELL_STUB_API_PATHS: Record<string, string> = Object.fromEntries(
  DASHBOARD_ROUTE_DEFS.filter(
    (d): d is DashboardRouteDef & { surface: 'stub'; stubApiPath: string } =>
      d.surface === 'stub',
  ).map((d) => [d.path, d.stubApiPath]),
)

export function isShellStubDashboardPath(path: string): boolean {
  return Object.prototype.hasOwnProperty.call(SHELL_STUB_API_PATHS, path)
}
