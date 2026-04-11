import { useRoleStore } from '@/stores/role-store'
import { t } from '@/lib/i18n'
import type { Role } from '@/types/role'

const titles: Record<Role, string> = {
  admin: 'Admin overview',
  leader: 'Leader overview',
  team: 'Your workspace',
}

export function DashboardHomePage() {
  const role = useRoleStore((s) => s.role)

  return (
    <div className="max-w-xl space-y-2">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {t('appTitle')}
      </p>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">
        {titles[role]}
      </h1>
      <p className="text-sm text-muted-foreground">{t('appTagline')}</p>
    </div>
  )
}
