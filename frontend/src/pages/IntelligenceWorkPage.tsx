import { Navigate } from 'react-router-dom'

import { useMetaQuery } from '@/hooks/use-meta-query'

type Props = {
  title: string
}

/**
 * Gated by `GET /api/v1/meta` → `features.intelligence` (env `FEATURE_INTELLIGENCE`).
 * Product-only area — no bundled third-party assistants.
 */
export function IntelligenceWorkPage({ title }: Props) {
  const { data, isPlaceholderData } = useMetaQuery()

  if (!isPlaceholderData && data && !data.features.intelligence) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">
        This section is reserved for <strong>in-house</strong> signals and workflows (scores, queues, rules you
        control). It is <strong>not</strong> a slot for third-party “AI assistants”.
      </p>
      <p className="text-sm text-muted-foreground">
        Toggle visibility via API env <code className="rounded bg-white/10 px-1.5 py-0.5 text-xs">FEATURE_INTELLIGENCE</code>{' '}
        (see <code className="rounded bg-white/10 px-1.5 py-0.5 text-xs">GET /api/v1/meta</code>). Wire real features
        here when product defines them.
      </p>
    </div>
  )
}
