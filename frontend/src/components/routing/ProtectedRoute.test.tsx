import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ProtectedRoute } from '@/components/routing/ProtectedRoute'

function renderProtected(initialPath: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/private" element={<ProtectedRoute />}>
            <Route index element={<p>Protected content</p>} />
          </Route>
          <Route path="/login" element={<p>Login screen</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            authenticated: false,
            role: null,
            user_id: null,
            email: null,
          }),
          { status: 200 },
        ),
      ),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects to login when /auth/me is not authenticated', async () => {
    renderProtected('/private')
    await waitFor(() => {
      expect(screen.getByText('Login screen')).toBeInTheDocument()
    })
  })

  it('renders child when /auth/me reports authenticated', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          authenticated: true,
          role: 'admin',
          user_id: 1,
          email: 'dev-admin@myle.local',
        }),
        { status: 200 },
      ),
    )
    renderProtected('/private')
    await waitFor(() => {
      expect(screen.getByText('Protected content')).toBeInTheDocument()
    })
  })
})
