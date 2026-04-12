/**
 * Dashboard home: quick actions — **core journey only** (see `docs/CORE_APP_STRUCTURE.md`).
 * Who may open each path = `dashboard-route-roles.json` + registry (`routeDefAccessible`);
 * labels = `resolveTitleForPath` / registry.
 */
import type { LucideIcon } from 'lucide-react'
import {
  ClipboardCheck,
  ClipboardList,
  FileBarChart,
  GraduationCap,
  Kanban,
  Megaphone,
  Sparkles,
  Users,
  Wallet,
} from 'lucide-react'

import {
  type ClientNavFlags,
  getDashboardChildRoute,
  resolveTitleForPath,
  routeDefAccessible,
} from '@/config/dashboard-registry'
import type { Role } from '@/types/role'

export const DASHBOARD_HOME_OVERVIEW_TITLE: Record<Role, string> = {
  admin: 'Admin overview',
  leader: 'Leader overview',
  team: 'Your workspace',
}

/** Display order — spine: leads → workboard → pool → wallet → recharge → training → report → approvals → team reports → notice → intelligence (if enabled). */
const HOME_QUICK_ACTION_PATHS: readonly string[] = [
  'work/leads',
  'work/workboard',
  'work/lead-pool',
  'work/lead-pool-admin',
  'finance/wallet',
  'finance/recharge-request',
  'system/training',
  'other/daily-report',
  'team/enrollment-approvals',
  'team/reports',
  'other/notice-board',
  'intelligence',
]

const PATH_ICONS: Partial<Record<string, LucideIcon>> = {
  'work/leads': Users,
  'work/workboard': Kanban,
  'work/lead-pool': Users,
  'work/lead-pool-admin': Users,
  'finance/wallet': Wallet,
  'finance/recharge-request': Wallet,
  'system/training': GraduationCap,
  'other/daily-report': ClipboardList,
  'team/enrollment-approvals': ClipboardCheck,
  'team/reports': FileBarChart,
  'other/notice-board': Megaphone,
  intelligence: Sparkles,
}

export type HomeQuickAction = {
  path: string
  to: string
  label: string
  Icon: LucideIcon
  /** Lead pool total when relevant */
  badgeCount?: number
}

export function getHomeQuickActions(
  role: Role,
  flags: ClientNavFlags,
  opts: { poolTotal: number },
): HomeQuickAction[] {
  const out: HomeQuickAction[] = []
  for (const path of HOME_QUICK_ACTION_PATHS) {
    const def = getDashboardChildRoute(path)
    if (!def) continue
    if (!routeDefAccessible(def, role, flags)) continue
    const Icon = PATH_ICONS[path]
    if (!Icon) continue
    const label = resolveTitleForPath(path, role) ?? def.label
    const poolPaths = new Set(['work/lead-pool', 'work/lead-pool-admin'])
    const badgeCount =
      poolPaths.has(path) && opts.poolTotal > 0 ? opts.poolTotal : undefined
    out.push({
      path,
      to: `/dashboard/${path}`,
      label,
      Icon,
      badgeCount,
    })
  }
  return out
}
