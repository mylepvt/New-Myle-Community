import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

async function fetchHello(): Promise<{ message: string }> {
  const res = await apiFetch('/api/v1/hello')
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json()
}

export function useHelloQuery() {
  return useQuery({
    queryKey: ['hello'],
    queryFn: fetchHello,
  })
}
