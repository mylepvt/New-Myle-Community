/** Dashboard child paths that map to `SystemStubResponse` GET endpoints. */

export const SHELL_STUB_API_PATHS: Record<string, string> = {
  'execution/at-risk-leads': '/api/v1/execution/at-risk-leads',
  'execution/lead-ledger': '/api/v1/execution/lead-ledger',
  'team/reports': '/api/v1/team/reports',
  'team/approvals': '/api/v1/team/approvals',
  'finance/budget-export': '/api/v1/finance/budget-export',
  'finance/monthly-targets': '/api/v1/finance/monthly-targets',
  'finance/lead-pool': '/api/v1/finance/lead-pool',
  'other/leaderboard': '/api/v1/other/leaderboard',
  'other/notice-board': '/api/v1/other/notice-board',
  'other/live-session': '/api/v1/other/live-session',
  'other/training': '/api/v1/other/training',
  'other/daily-report': '/api/v1/other/daily-report',
  'settings/app': '/api/v1/settings/app',
  'settings/help': '/api/v1/settings/help',
  'settings/all-members': '/api/v1/settings/all-members',
  'settings/org-tree': '/api/v1/settings/org-tree',
}

export function isShellStubDashboardPath(path: string): boolean {
  return Object.prototype.hasOwnProperty.call(SHELL_STUB_API_PATHS, path)
}
