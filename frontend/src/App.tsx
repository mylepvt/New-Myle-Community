import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '@/components/routing/ProtectedRoute'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Skeleton } from '@/components/ui/skeleton'
import { DashboardHomePage } from '@/pages/DashboardHomePage'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

const DashboardNestedPage = lazy(async () => {
  const m = await import('@/pages/DashboardNestedPage')
  return { default: m.DashboardNestedPage }
})

function DashboardRouteFallback() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-24 w-full max-w-2xl" />
    </div>
  )
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<DashboardHomePage />} />
          <Route
            path="*"
            element={
              <Suspense fallback={<DashboardRouteFallback />}>
                <DashboardNestedPage />
              </Suspense>
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
