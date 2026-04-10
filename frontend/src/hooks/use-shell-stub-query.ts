import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type ShellStubResponse = {
  items: Record<string, unknown>[]
  total: number
  note: string | null
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({}))
  const msg =
    typeof err === 'object' && err !== null && 'error' in err
      ? String((err as { error?: { message?: string } }).error?.message ?? res.statusText)
      : res.statusText
  throw new Error(msg || `HTTP ${res.status}`)
}

async function fetchShellStub(apiPath: string): Promise<ShellStubResponse> {
  const res = await apiFetch(apiPath)
  if (!res.ok) await parseError(res)
  return res.json()
}

export function useShellStubQuery(apiPath: string, enabled = true) {
  return useQuery({
    queryKey: ['shell-stub', apiPath],
    queryFn: () => fetchShellStub(apiPath),
    enabled,
  })
}
