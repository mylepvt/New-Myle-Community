import { Loader2 } from 'lucide-react'
import * as React from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type EmptyStateProps = {
  title: string
  description?: string
  className?: string
  children?: React.ReactNode
}

export function EmptyState({
  title,
  description,
  className,
  children,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface/30 px-6 py-10 text-center',
        className,
      )}
    >
      <p className="font-heading text-ds-h3 text-foreground">{title}</p>
      {description ? (
        <p className="mt-2 max-w-sm text-ds-body text-muted-foreground">
          {description}
        </p>
      ) : null}
      {children ? <div className="mt-4">{children}</div> : null}
    </div>
  )
}

type LoadingStateProps = {
  label?: string
  className?: string
}

export function LoadingState({ label, className }: LoadingStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-10 text-muted-foreground',
        className,
      )}
      role="status"
      aria-busy
      aria-live="polite"
    >
      <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
      {label ? <p className="text-ds-caption">{label}</p> : null}
    </div>
  )
}

type ErrorStateProps = {
  title?: string
  message: string
  onRetry?: () => void
  retryLabel?: string
  className?: string
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  retryLabel = 'Retry',
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-destructive/35 bg-destructive/10 px-6 py-8 text-center',
        className,
      )}
      role="alert"
    >
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-2 max-w-md text-ds-body text-muted-foreground">
        {message}
      </p>
      {onRetry ? (
        <Button
          type="button"
          variant="secondary"
          className="mt-4"
          onClick={onRetry}
        >
          {retryLabel}
        </Button>
      ) : null}
    </div>
  )
}
