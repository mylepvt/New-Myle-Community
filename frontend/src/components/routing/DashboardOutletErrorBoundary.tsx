import { Component, type ErrorInfo, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'

type Props = { children: ReactNode }

type State = { error: Error | null }

export class DashboardOutletErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Dashboard route error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="max-w-lg space-y-3 rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-sm">
          <p className="font-semibold text-destructive">This view crashed</p>
          <p className="text-muted-foreground">
            {this.state.error.message || 'Unexpected error'}
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}
