import { Suspense, lazy, useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'

import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { InstallAppBanner } from '@/components/pwa/InstallAppBanner'
import { ProtectedRoute } from '@/components/routing/ProtectedRoute'
import { Skeleton } from '@/components/ui/skeleton'
import { DashboardHomePage } from '@/pages/DashboardHomePage'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { t } from '@/lib/i18n'

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
  useEffect(() => {
    document.title = t('appTitle')
  }, [])

  return (
    <>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

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
      <InstallAppBanner />
    </>
  )
}
