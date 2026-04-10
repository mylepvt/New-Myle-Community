type Props = {
  title: string
}

export function DashboardPlaceholderPage({ title }: Props) {
  return (
    <div className="max-w-xl">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">
        {title}
      </h1>
    </div>
  )
}
