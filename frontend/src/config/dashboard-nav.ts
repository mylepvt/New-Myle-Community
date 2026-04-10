import type { Role } from '@/types/role'

/** One sidebar link; `path` empty = dashboard home (index). */
export type DashboardNavItem = {
  path: string
  label: string
  roles: Role[]
  end?: boolean
  /** Override label in sidebar per role (e.g. All Leads vs My Leads). */
  labelByRole?: Partial<Record<Role, string>>
  /** Hide unless AI module is enabled (future: drive from API). */
  requiresAi?: boolean
}

export type DashboardNavSection = {
  id: string
  /** Empty = no section heading (avoids duplicate “Home” + “Dashboard”). */
  label: string
  items: DashboardNavItem[]
}

/**
 * Information architecture inspired by legacy Myle dashboard — UI/colours are not copied.
 */
export const dashboardNavSections: DashboardNavSection[] = [
  {
    id: 'main',
    label: '',
    items: [
      {
        path: '',
        label: 'Dashboard',
        roles: ['admin', 'leader', 'team'],
        end: true,
      },
    ],
  },
  {
    id: 'execution',
    label: 'Execution',
    items: [
      {
        path: 'execution/at-risk-leads',
        label: 'At-risk leads',
        roles: ['admin'],
      },
      {
        path: 'execution/weak-members',
        label: 'Weak members',
        roles: ['admin'],
      },
      {
        path: 'execution/leak-map',
        label: 'Leak map',
        roles: ['admin'],
      },
      {
        path: 'execution/lead-ledger',
        label: 'Lead ledger',
        roles: ['admin'],
      },
    ],
  },
  {
    id: 'work',
    label: 'Work',
    items: [
      {
        path: 'work/leads',
        label: 'My Leads',
        labelByRole: { admin: 'All Leads' },
        roles: ['admin', 'leader', 'team'],
      },
      {
        path: 'work/workboard',
        label: 'Workboard',
        roles: ['admin', 'leader', 'team'],
      },
      {
        path: 'work/follow-ups',
        label: 'Follow-ups',
        roles: ['admin', 'leader'],
      },
      {
        path: 'work/retarget',
        label: 'Retarget',
        roles: ['admin', 'leader', 'team'],
      },
      {
        path: 'work/lead-flow',
        label: 'Lead flow',
        roles: ['leader', 'team'],
      },
      {
        path: 'work/archived',
        label: 'Archived leads',
        roles: ['admin', 'leader', 'team'],
      },
      {
        path: 'work/add-lead',
        label: 'Add lead',
        roles: ['admin'],
      },
      {
        path: 'work/lead-pool-admin',
        label: 'Admin lead pool',
        roles: ['admin'],
      },
      {
        path: 'work/recycle-bin',
        label: 'Recycle bin',
        roles: ['admin'],
      },
      {
        path: 'intelligence',
        label: 'AI intelligence',
        roles: ['admin', 'team'],
        requiresAi: true,
      },
    ],
  },
  {
    id: 'team',
    label: 'Team',
    items: [
      {
        path: 'team/members',
        label: 'Members',
        roles: ['admin'],
      },
      {
        path: 'team/reports',
        label: 'Reports',
        roles: ['admin'],
      },
      {
        path: 'team/approvals',
        label: 'Approvals',
        roles: ['admin'],
      },
      {
        path: 'team/enrollment-approvals',
        label: '₹196 approvals',
        roles: ['admin', 'leader'],
      },
      {
        path: 'team/my-team',
        label: 'My team',
        roles: ['leader'],
      },
    ],
  },
  {
    id: 'system',
    label: 'System',
    items: [
      {
        path: 'system/training',
        label: 'Training (admin)',
        roles: ['admin'],
      },
      {
        path: 'system/decision-engine',
        label: 'Decision engine',
        roles: ['admin'],
      },
      {
        path: 'system/coaching',
        label: 'Coaching panel',
        roles: ['admin', 'leader'],
      },
    ],
  },
  {
    id: 'analytics',
    label: 'Analytics',
    items: [
      {
        path: 'analytics/activity-log',
        label: 'Activity log',
        roles: ['admin'],
      },
      {
        path: 'analytics/day-2-report',
        label: 'Day 2 test report',
        roles: ['admin'],
      },
    ],
  },
  {
    id: 'finance',
    label: 'Finance',
    items: [
      {
        path: 'finance/recharges',
        label: 'Recharges',
        roles: ['admin'],
      },
      {
        path: 'finance/budget-export',
        label: 'Budget export',
        roles: ['admin'],
      },
      {
        path: 'finance/monthly-targets',
        label: 'Monthly targets',
        roles: ['admin'],
      },
      {
        path: 'finance/wallet',
        label: 'My wallet',
        roles: ['leader', 'team'],
      },
      {
        path: 'finance/lead-pool',
        label: 'Lead pool',
        roles: ['leader', 'team'],
      },
    ],
  },
  {
    id: 'other',
    label: 'Other',
    items: [
      {
        path: 'other/leaderboard',
        label: 'Leaderboard',
        roles: ['admin', 'leader', 'team'],
      },
      {
        path: 'other/notice-board',
        label: 'Notice board',
        roles: ['admin', 'leader', 'team'],
      },
      {
        path: 'other/live-session',
        label: 'Live session',
        roles: ['admin', 'leader', 'team'],
      },
      {
        path: 'other/training',
        label: 'My training',
        roles: ['leader', 'team'],
      },
      {
        path: 'other/daily-report',
        label: 'Daily report',
        roles: ['leader', 'team'],
      },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    items: [
      {
        path: 'settings/app',
        label: 'General',
        roles: ['admin'],
      },
      {
        path: 'settings/help',
        label: 'Help',
        roles: ['admin'],
      },
      {
        path: 'settings/all-members',
        label: 'All members',
        roles: ['admin'],
      },
      {
        path: 'settings/org-tree',
        label: 'Org tree',
        roles: ['admin'],
      },
    ],
  },
]

/** AI-gated items visible until you wire a real feature flag from the API. */
const AI_ENABLED = true

export function itemVisible(item: DashboardNavItem, role: Role): boolean {
  if (!item.roles.includes(role)) {
    return false
  }
  if (item.requiresAi && !AI_ENABLED) {
    return false
  }
  return true
}

export function filterDashboardNav(role: Role): DashboardNavSection[] {
  return dashboardNavSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => itemVisible(item, role)),
    }))
    .filter((section) => section.items.length > 0)
}

export function resolveItemLabel(item: DashboardNavItem, role: Role): string {
  return item.labelByRole?.[role] ?? item.label
}

export const dashboardChildPathSet = new Set(
  dashboardNavSections.flatMap((s) =>
    s.items.map((i) => i.path).filter((p): p is string => Boolean(p)),
  ),
)

export function resolveTitleForPath(
  path: string,
  role: Role,
): string | undefined {
  for (const section of dashboardNavSections) {
    for (const item of section.items) {
      if (item.path === path) {
        return resolveItemLabel(item, role)
      }
    }
  }
  return undefined
}
