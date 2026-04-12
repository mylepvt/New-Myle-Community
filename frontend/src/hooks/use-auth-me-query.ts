import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type MeResponse = {
  authenticated: boolean
  role: string | null
  user_id: number | null
  /** Globally unique account id (primary). */
  fbo_id: string | null
  username: string | null
  email: string | null
  /** Legacy session display_name / derived label (username or email local-part). */
  display_name: string | null
  /** JWT `ver` claim (legacy AUTH_SESSION_VERSION parity). */
  auth_version: number | null
  /** Legacy `training_status` (e.g. pending, completed, not_required). */
  training_status: string | null
  /** When true, full dashboard is gated until training is completed (legacy). */
  training_required: boolean | null
  /** pending | approved | rejected */
  registration_status: string | null
}

export async function fetchAuthMe(): Promise<MeResponse> {
  const res = await apiFetch('/api/v1/auth/me')
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  const raw = (await res.json()) as Partial<MeResponse>
  return {
    authenticated: Boolean(raw.authenticated),
    role: raw.role ?? null,
    user_id: raw.user_id ?? null,
    fbo_id: raw.fbo_id ?? null,
    username: raw.username ?? null,
    email: raw.email ?? null,
    display_name: raw.display_name ?? null,
    auth_version:
      typeof raw.auth_version === 'number' ? raw.auth_version : null,
    training_status:
      typeof raw.training_status === 'string' ? raw.training_status : null,
    training_required:
      typeof raw.training_required === 'boolean' ? raw.training_required : null,
    registration_status:
      typeof raw.registration_status === 'string'
        ? raw.registration_status
        : null,
  }
}

export type UseAuthMeQueryOptions = {
  /** Use `0` on route gates so each visit revalidates against the server. */
  staleTime?: number
  refetchOnMount?: boolean | 'always'
}

export function useAuthMeQuery(options?: UseAuthMeQueryOptions) {
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: fetchAuthMe,
    staleTime: options?.staleTime ?? 30_000,
    refetchOnMount: options?.refetchOnMount ?? true,
  })
}
