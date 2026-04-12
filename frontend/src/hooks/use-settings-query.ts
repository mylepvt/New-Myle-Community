import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type UserProfileResponse = {
  id: number
  fbo_id: string
  username?: string
  email: string
  role: string
  phone?: string
  name?: string
  upline_user_id?: number
  registration_status: string
  training_required: boolean
  training_status: string
  access_blocked: boolean
  discipline_status: string
  joining_date?: string
  created_at: string
}

export type UserProfileUpdateRequest = {
  username?: string
  phone?: string
  name?: string
  joining_date?: string
  upline_user_id?: number
  registration_status?: string
  training_required?: boolean
  training_status?: string
  access_blocked?: boolean
  discipline_status?: string
}

export type UserPreferencesResponse = {
  email_notifications: boolean
  push_notifications: boolean
  daily_report_reminders: boolean
  lead_assignment_alerts: boolean
  payment_notifications: boolean
  training_reminders: boolean
  weekly_summary: boolean
  language: string
  timezone: string
  theme: string
}

export type UserPreferencesUpdateRequest = {
  email_notifications?: boolean
  push_notifications?: boolean
  daily_report_reminders?: boolean
  lead_assignment_alerts?: boolean
  payment_notifications?: boolean
  training_reminders?: boolean
  weekly_summary?: boolean
  language?: string
  timezone?: string
  theme?: string
}

export type SystemConfigurationResponse = {
  app_settings: Record<string, string>
  system_defaults: {
    default_role: string
    require_training: boolean
    auto_approve_registrations: boolean
    default_language: string
    default_timezone: string
    session_timeout: number
    max_upload_size: number
    supported_languages: string[]
    supported_timezones: string[]
  }
  feature_flags: {
    enable_wallet: boolean
    enable_training: boolean
    enable_reports: boolean
    enable_analytics: boolean
    enable_notifications: boolean
  }
}

export type SystemUsersSummaryResponse = {
  total_users: number
  by_role: Record<string, number>
  by_status: Record<string, number>
  blocked_users: number
  by_training_status: Record<string, number>
}

export type AppSettingsResponse = {
  settings: Record<string, string>
}

export type AppSettingUpdateRequest = {
  key: string
  value: string
}

export type PasswordChangeRequest = {
  current_password: string
  new_password: string
  confirm_password: string
}

export type EmailChangeRequest = {
  new_email: string
  current_password: string
}

// Settings API functions
async function fetchUserProfile(): Promise<UserProfileResponse> {
  const res = await apiFetch('/api/v1/settings-enhanced/profile')
  if (!res.ok) {
    throw new Error(`User profile HTTP ${res.status}`)
  }
  return res.json()
}

async function updateUserProfile(request: UserProfileUpdateRequest): Promise<{ message: string }> {
  const res = await apiFetch('/api/v1/settings-enhanced/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    throw new Error(`Update profile HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchUserPreferences(): Promise<UserPreferencesResponse> {
  const res = await apiFetch('/api/v1/settings-enhanced/preferences')
  if (!res.ok) {
    throw new Error(`User preferences HTTP ${res.status}`)
  }
  return res.json()
}

async function updateUserPreferences(request: UserPreferencesUpdateRequest): Promise<{ message: string }> {
  const res = await apiFetch('/api/v1/settings-enhanced/preferences', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    throw new Error(`Update preferences HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchSystemConfiguration(): Promise<SystemConfigurationResponse> {
  const res = await apiFetch('/api/v1/settings-enhanced/system/configuration')
  if (!res.ok) {
    throw new Error(`System configuration HTTP ${res.status}`)
  }
  return res.json()
}

async function updateSystemConfiguration(request: Record<string, any>): Promise<{ message: string }> {
  const res = await apiFetch('/api/v1/settings-enhanced/system/configuration', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    throw new Error(`Update system configuration HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchAppSettings(): Promise<AppSettingsResponse> {
  const res = await apiFetch('/api/v1/settings-enhanced/system/app-settings')
  if (!res.ok) {
    throw new Error(`App settings HTTP ${res.status}`)
  }
  return res.json()
}

async function updateAppSetting(request: AppSettingUpdateRequest): Promise<{ message: string }> {
  const res = await apiFetch('/api/v1/settings-enhanced/system/app-settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    throw new Error(`Update app setting HTTP ${res.status}`)
  }
  return res.json()
}

async function deleteAppSetting(key: string): Promise<{ message: string }> {
  const res = await apiFetch(`/api/v1/settings-enhanced/system/app-settings/${key}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    throw new Error(`Delete app setting HTTP ${res.status}`)
  }
  return res.json()
}

async function fetchSystemUsersSummary(): Promise<SystemUsersSummaryResponse> {
  const res = await apiFetch('/api/v1/settings-enhanced/system/users-summary')
  if (!res.ok) {
    throw new Error(`Users summary HTTP ${res.status}`)
  }
  return res.json()
}

async function changePassword(request: PasswordChangeRequest): Promise<{ success: boolean; message: string }> {
  const res = await apiFetch('/api/v1/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    throw new Error(`Change password HTTP ${res.status}`)
  }
  return res.json()
}

async function changeEmail(request: EmailChangeRequest): Promise<{ success: boolean; message: string; verification_required?: boolean }> {
  const res = await apiFetch('/api/v1/auth/change-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    throw new Error(`Change email HTTP ${res.status}`)
  }
  return res.json()
}

// Settings hooks
export function useUserProfileQuery() {
  return useQuery({
    queryKey: ['settings', 'profile'],
    queryFn: fetchUserProfile,
    staleTime: 30_000,
  })
}

export function useUserProfileUpdateMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: updateUserProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'profile'] })
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}

export function useUserPreferencesQuery() {
  return useQuery({
    queryKey: ['settings', 'preferences'],
    queryFn: fetchUserPreferences,
    staleTime: 30_000,
  })
}

export function useUserPreferencesUpdateMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: updateUserPreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'preferences'] })
    },
  })
}

export function useSystemConfigurationQuery() {
  return useQuery({
    queryKey: ['settings', 'system', 'configuration'],
    queryFn: fetchSystemConfiguration,
    staleTime: 60_000,
  })
}

export function useSystemConfigurationUpdateMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: updateSystemConfiguration,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'system', 'configuration'] })
      queryClient.invalidateQueries({ queryKey: ['settings', 'system', 'app-settings'] })
    },
  })
}

export function useAppSettingsQuery() {
  return useQuery({
    queryKey: ['settings', 'system', 'app-settings'],
    queryFn: fetchAppSettings,
    staleTime: 60_000,
  })
}

export function useAppSettingUpdateMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: updateAppSetting,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'system', 'app-settings'] })
      queryClient.invalidateQueries({ queryKey: ['settings', 'system', 'configuration'] })
    },
  })
}

export function useAppSettingDeleteMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: deleteAppSetting,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'system', 'app-settings'] })
      queryClient.invalidateQueries({ queryKey: ['settings', 'system', 'configuration'] })
    },
  })
}

export function useSystemUsersSummaryQuery() {
  return useQuery({
    queryKey: ['settings', 'system', 'users-summary'],
    queryFn: fetchSystemUsersSummary,
    staleTime: 60_000,
  })
}

export function usePasswordChangeMutation() {
  return useMutation({
    mutationFn: changePassword,
  })
}

export function useEmailChangeMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: changeEmail,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}
