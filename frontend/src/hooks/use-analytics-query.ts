import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type TeamPerformanceResponse = {
  period: string
  team_size: number
  reports: {
    total_reports: number
    total_calls: number
    calls_picked: number
    enrollments: number
    payments: number
    avg_daily_calls: number
    pickup_rate: number
  }
  leads: {
    total_leads: number
    converted_leads: number
    paid_leads: number
    conversion_rate: number
    payment_rate: number
  }
  scores: {
    total_points: number
    avg_daily_points: number
    days_with_reports: number
  }
}

export type IndividualPerformanceResponse = {
  period: string
  reports: {
    total_reports: number
    total_calls: number
    total_enrollments: number
    total_payments: number
    avg_daily_calls: number
  }
  leads: {
    total_leads: number
    converted_leads: number
    paid_leads: number
  }
  scores: {
    total_points: number
    days_with_reports: number
  }
  daily_trends: Array<{
    date: string
    calls: number
    enrollments: number
    payments: number
    points: number
  }>
}

export type LeaderboardResponse = {
  leaderboard: Array<{
    rank: number
    user_id: number
    username: string
    fbo_id?: string
    total_points: number
    days_with_reports: number
    avg_daily_points: number
    total_leads: number
    converted_leads: number
  }>
  period: string
}

export type SystemOverviewResponse = {
  period: string
  users: {
    active_users: number
    total_reports: number
  }
  reports: {
    total_reports: number
    total_calls: number
    total_enrollments: number
    total_payments: number
    avg_calls_per_user: number
  }
  leads: {
    total_leads: number
    converted_leads: number
    paid_leads: number
    conversion_rate: number
  }
  wallet: {
    active_wallets: number
    total_credits: number
    total_debits: number
    net_volume: number
  }
}

export type DailyTrendsResponse = {
  trends: Array<{
    date: string
    reports_count: number
    total_calls: number
    total_enrollments: number
    total_payments: number
    avg_calls_per_report: number
  }>
  period: string
}

export type ReportSubmissionRequest = {
  report_date: string
  total_calling: number
  calls_picked: number
  wrong_numbers: number
  enrollments_done: number
  pending_enroll: number
  underage: number
  plan_2cc: number
  seat_holdings: number
  leads_educated: number
  pdf_covered: number
  videos_sent_actual: number
  calls_made_actual: number
  payments_actual: number
  remarks?: string
}

export type ReportSubmissionResponse = {
  success: boolean
  message: string
  points_awarded: number
  report_id: number
}

// Analytics API functions
async function fetchTeamPerformance(days = 30): Promise<TeamPerformanceResponse> {
  const res = await apiFetch(`/api/v1/analytics/team-performance?days=${days}`)
  if (!res.ok) {
    throw new Error(`Team performance HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchIndividualPerformance(userId?: number, days = 30): Promise<IndividualPerformanceResponse> {
  const params = new URLSearchParams({ days: days.toString() })
  if (userId) params.set('target_user_id', userId.toString())
  
  const res = await apiFetch(`/api/v1/analytics/individual-performance?${params}`)
  if (!res.ok) {
    throw new Error(`Individual performance HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchLeaderboard(days = 30): Promise<LeaderboardResponse> {
  const res = await apiFetch(`/api/v1/analytics/leaderboard?days=${days}`)
  if (!res.ok) {
    throw new Error(`Leaderboard HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchSystemOverview(days = 30): Promise<SystemOverviewResponse> {
  const res = await apiFetch(`/api/v1/analytics/system-overview?days=${days}`)
  if (!res.ok) {
    throw new Error(`System overview HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchDailyTrends(userId?: number, days = 30): Promise<DailyTrendsResponse> {
  const params = new URLSearchParams({ days: days.toString() })
  if (userId) params.set('target_user_id', userId.toString())
  
  const res = await apiFetch(`/api/v1/analytics/daily-trends?${params}`)
  if (!res.ok) {
    throw new Error(`Daily trends HTTP ${res.status}`)
  }
  return res.json()
}

async function submitDailyReport(request: ReportSubmissionRequest): Promise<ReportSubmissionResponse> {
  const res = await apiFetch('/api/v1/reports/daily', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    throw new Error(`Daily report submission HTTP ${res.status}`)
  }
  return res.json()
}

// Analytics hooks
export function useTeamPerformanceQuery(days = 30) {
  return useQuery({
    queryKey: ['analytics', 'team-performance', days],
    queryFn: () => fetchTeamPerformance(days),
    staleTime: 30_000,
  })
}

export function useIndividualPerformanceQuery(userId?: number, days = 30) {
  return useQuery({
    queryKey: ['analytics', 'individual-performance', userId, days],
    queryFn: () => fetchIndividualPerformance(userId, days),
    staleTime: 30_000,
  })
}

export function useLeaderboardQuery(days = 30) {
  return useQuery({
    queryKey: ['analytics', 'leaderboard', days],
    queryFn: () => fetchLeaderboard(days),
    staleTime: 60_000,
  })
}

export function useSystemOverviewQuery(days = 30) {
  return useQuery({
    queryKey: ['analytics', 'system-overview', days],
    queryFn: () => fetchSystemOverview(days),
    staleTime: 60_000,
  })
}

export function useDailyTrendsQuery(userId?: number, days = 30) {
  return useQuery({
    queryKey: ['analytics', 'daily-trends', userId, days],
    queryFn: () => fetchDailyTrends(userId, days),
    staleTime: 30_000,
  })
}

export function useDailyReportSubmissionMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: submitDailyReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analytics'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}
