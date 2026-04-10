export const apiBase =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

export function apiUrl(path: string): string {
  const base = apiBase.replace(/\/$/, '')
  const p = path.startsWith('/') ? path : `/${path}`
  return `${base}${p}`
}

/** Browser fetch with cookies (JWT dev auth). */
export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(apiUrl(path), {
    credentials: 'include',
    ...init,
  })
}
