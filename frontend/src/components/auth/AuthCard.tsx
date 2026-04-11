import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

type AuthCardProps = {
  /** Header visual: centered icon (login) or split icon + titles (register). */
  variant: 'center' | 'split'
  icon: LucideIcon
  title: string
  subtitle: string
  children: ReactNode
  footer?: ReactNode
  /** Optional class on outer card */
  className?: string
}

export function AuthCard({
  variant,
  icon: Icon,
  title,
  subtitle,
  children,
  footer,
  className,
}: AuthCardProps) {
  return (
    <div
      className={cn(
        'w-full max-w-[min(100%,26rem)] overflow-hidden rounded-[1.35rem] border border-white/[0.08]',
        'bg-card shadow-[0_28px_80px_-32px_rgba(0,0,0,0.85)]',
        className,
      )}
    >
      <div
        className={cn(
          'relative bg-gradient-to-br from-primary via-[hsl(68_100%_46%)] to-[hsl(72_90%_38%)]',
          variant === 'center' ? 'px-6 pb-8 pt-9 text-center' : 'px-5 pb-6 pt-6 sm:px-6',
        )}
      >
        {variant === 'center' ? (
          <>
            <div className="mx-auto mb-4 flex size-[4.25rem] items-center justify-center rounded-full border border-primary-foreground/25 bg-primary-foreground/15 shadow-inner backdrop-blur-sm">
              <Icon className="size-9 text-primary-foreground" aria-hidden />
            </div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-primary-foreground">
              {title}
            </h1>
            <p className="mt-1.5 text-sm font-medium text-primary-foreground/88">
              {subtitle}
            </p>
          </>
        ) : (
          <div className="flex items-start gap-4">
            <div className="flex size-14 shrink-0 items-center justify-center rounded-full border border-primary-foreground/25 bg-primary-foreground/15 shadow-inner">
              <Icon className="size-7 text-primary-foreground" aria-hidden />
            </div>
            <div className="min-w-0 flex-1 pt-0.5 text-left">
              <h1 className="font-heading text-lg font-bold leading-snug tracking-tight text-primary-foreground sm:text-xl">
                {title}
              </h1>
              <p className="mt-1 text-sm font-medium leading-relaxed text-primary-foreground/88">
                {subtitle}
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-5 bg-card px-5 py-6 sm:px-7">{children}</div>

      {footer ? (
        <div className="border-t border-white/[0.08] bg-card/80 px-5 py-4 text-center sm:px-7">
          {footer}
        </div>
      ) : null}
    </div>
  )
}
