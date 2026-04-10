import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type MeResponse = {
  authenticated: boolean
  role: string | null
  user_id: number | null
  email: string | null
}

async function fetchMe(): Promise<MeResponse> {
  const res = await apiFetch('/api/v1/auth/me')
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  const raw = (await res.json()) as Partial<MeResponse>
  return {
    authenticated: Boolean(raw.authenticated),
    role: raw.role ?? null,
    user_id: raw.user_id ?? null,
    email: raw.email ?? null,
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
    queryFn: fetchMe,
    staleTime: options?.staleTime ?? 30_000,
    refetchOnMount: options?.refetchOnMount ?? true,
  })
}
