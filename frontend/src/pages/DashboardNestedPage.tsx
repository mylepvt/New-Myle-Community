import { Navigate, useParams } from 'react-router-dom'

import { dashboardChildPathSet, resolveTitleForPath } from '@/config/dashboard-nav'
import { DashboardPlaceholderPage } from '@/pages/DashboardPlaceholderPage'
import { LeadsWorkPage } from '@/pages/LeadsWorkPage'
import { useRoleStore } from '@/stores/role-store'

/**
 * Single outlet for all `/dashboard/*` segments — avoids dozens of duplicate routes.
 */
export function DashboardNestedPage() {
  const { '*': splat } = useParams()
  const path = (splat ?? '').replace(/^\/+|\/+$/g, '')
  const role = useRoleStore((s) => s.role)

  if (!path || !dashboardChildPathSet.has(path)) {
    return <Navigate to="/dashboard" replace />
  }

  const title = resolveTitleForPath(path, role) ?? path
  if (path === 'work/leads') {
    return <LeadsWorkPage title={title} />
  }
  return <DashboardPlaceholderPage title={title} />
}
