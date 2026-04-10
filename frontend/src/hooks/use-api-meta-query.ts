import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type ApiMeta = {
  name: string
  api_version: number
}

async function fetchMeta(): Promise<ApiMeta> {
  const res = await apiFetch('/api/v1/meta')
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json()
}

export function useApiMetaQuery() {
  return useQuery({
    queryKey: ['api-meta'],
    queryFn: fetchMeta,
  })
}
