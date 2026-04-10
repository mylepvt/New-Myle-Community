import { Navigate, useParams } from 'react-router-dom'

import { dashboardChildPathSet, resolveTitleForPath } from '@/config/dashboard-nav'
import { SHELL_STUB_API_PATHS, isShellStubDashboardPath } from '@/config/shell-stub-routes'
import { DashboardPlaceholderPage } from '@/pages/DashboardPlaceholderPage'
import { LeadsWorkPage } from '@/pages/LeadsWorkPage'
import { FollowUpsWorkPage } from '@/pages/FollowUpsWorkPage'
import { IntelligenceWorkPage } from '@/pages/IntelligenceWorkPage'
import { LeadFlowPage } from '@/pages/LeadFlowPage'
import { LeadPoolWorkPage } from '@/pages/LeadPoolWorkPage'
import { RecycleBinWorkPage } from '@/pages/RecycleBinWorkPage'
import { TeamMembersPage } from '@/pages/TeamMembersPage'
import { MyTeamPage } from '@/pages/MyTeamPage'
import { EnrollmentApprovalsPage } from '@/pages/EnrollmentApprovalsPage'
import { AnalyticsSurfacePage } from '@/pages/AnalyticsSurfacePage'
import { SystemSurfacePage } from '@/pages/SystemSurfacePage'
import { RetargetWorkPage } from '@/pages/RetargetWorkPage'
import { WorkboardPage } from '@/pages/WorkboardPage'
import { ShellStubPage } from '@/pages/ShellStubPage'
import { WalletPage } from '@/pages/WalletPage'
import { FinanceRechargesPage } from '@/pages/FinanceRechargesPage'
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
  if (path === 'work/add-lead') {
    return <LeadsWorkPage title={title} listMode="active" />
  }
  if (path === 'work/leads') {
    return <LeadsWorkPage title={title} listMode="active" />
  }
  if (path === 'work/archived') {
    return <LeadsWorkPage title={title} listMode="archived" />
  }
  if (path === 'work/workboard') {
    return <WorkboardPage title={title} />
  }
  if (path === 'work/follow-ups') {
    return <FollowUpsWorkPage title={title} />
  }
  if (path === 'work/retarget') {
    return <RetargetWorkPage title={title} />
  }
  if (path === 'work/lead-flow') {
    return <LeadFlowPage title={title} />
  }
  if (path === 'work/lead-pool' || path === 'work/lead-pool-admin') {
    return <LeadPoolWorkPage title={title} />
  }
  if (path === 'work/recycle-bin') {
    return <RecycleBinWorkPage title={title} />
  }
  if (path === 'intelligence') {
    return <IntelligenceWorkPage title={title} />
  }
  if (path === 'team/members') {
    return <TeamMembersPage title={title} />
  }
  if (path === 'team/my-team') {
    return <MyTeamPage title={title} />
  }
  if (path === 'team/enrollment-approvals') {
    return <EnrollmentApprovalsPage title={title} />
  }
  if (path === 'system/training') {
    return <SystemSurfacePage title={title} surface="training" />
  }
  if (path === 'system/decision-engine') {
    return <SystemSurfacePage title={title} surface="decision-engine" />
  }
  if (path === 'system/coaching') {
    return <SystemSurfacePage title={title} surface="coaching" />
  }
  if (path === 'analytics/activity-log') {
    return <AnalyticsSurfacePage title={title} surface="activity-log" />
  }
  if (path === 'analytics/day-2-report') {
    return <AnalyticsSurfacePage title={title} surface="day-2-report" />
  }
  if (path === 'finance/wallet') {
    return <WalletPage title={title} />
  }
  if (path === 'finance/recharges') {
    return <FinanceRechargesPage title={title} />
  }
  if (isShellStubDashboardPath(path)) {
    return <ShellStubPage title={title} apiPath={SHELL_STUB_API_PATHS[path]} />
  }
  return <DashboardPlaceholderPage title={title} />
}
