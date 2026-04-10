import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-semibold text-foreground">404</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        This route is not part of the shell map yet.
      </p>
      <Link
        to="/"
        className="text-sm font-medium text-primary hover:underline"
      >
        Go home
      </Link>
    </div>
  )
}
