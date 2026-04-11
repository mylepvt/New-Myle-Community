import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1.5rem,env(safe-area-inset-top))]">
      <div className="surface-elevated w-full max-w-sm space-y-4 rounded-2xl p-8 text-center">
        <p className="text-sm font-medium text-muted-foreground">Error</p>
        <h1 className="text-4xl font-semibold tabular-nums tracking-tight text-foreground">
          404
        </h1>
        <p className="text-sm leading-relaxed text-muted-foreground">
          This page does not exist or has not been enabled for your account yet.
        </p>
        <Button asChild className="w-full gap-2">
          <Link to="/">
            <Home className="size-4" aria-hidden />
            Back to home
          </Link>
        </Button>
      </div>
    </div>
  )
}
