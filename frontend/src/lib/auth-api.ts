import { apiFetch } from '@/lib/api'
import type { Role } from '@/types/role'

export async function authDevLogin(role: Role): Promise<void> {
  const res = await apiFetch('/api/v1/auth/dev-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  })
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('Dev login is off (set AUTH_DEV_LOGIN_ENABLED on the API).')
    }
    throw new Error(`HTTP ${res.status}`)
  }
}

export async function authLogout(): Promise<void> {
  const res = await apiFetch('/api/v1/auth/logout', { method: 'POST' })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
}
