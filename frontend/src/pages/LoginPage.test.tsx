import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LoginPage } from '@/pages/LoginPage'

function mockMeta(authDevLogin: boolean) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/api/v1/meta')) {
      return new Response(
        JSON.stringify({
          name: 'myle-vl2',
          api_version: 1,
          environment: 'test',
          auth_dev_login_enabled: authDevLogin,
          features: { intelligence: true },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }
    return new Response(null, { status: 404 })
  })
}

function renderLogin() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    mockMeta(true)
  })
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders dev role sign-in and email/password form when meta allows dev login', async () => {
    renderLogin()
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /continue with preview role/i }),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByRole('heading', { name: /myle community/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /sign in/i }),
    ).toBeInTheDocument()
  })

  it('hides dev quick-login when meta auth_dev_login_enabled is false', async () => {
    vi.restoreAllMocks()
    mockMeta(false)
    renderLogin()
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /continue \(dev role\)/i })).not.toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(
      screen.getByText(/use your work email and password/i),
    ).toBeInTheDocument()
  })
})
