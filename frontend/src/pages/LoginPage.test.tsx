import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { LoginPage } from '@/pages/LoginPage'

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
  it('renders dev role sign-in and email/password form', () => {
    renderLogin()
    expect(screen.getByRole('heading', { name: /myle vl2/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue \(dev role\)/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^sign in$/i })).toBeInTheDocument()
  })
})
