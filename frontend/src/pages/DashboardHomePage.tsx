import { useRoleStore } from '@/stores/role-store'
import type { Role } from '@/types/role'

const titles: Record<Role, string> = {
  admin: 'Admin overview',
  leader: 'Leader overview',
  team: 'Your workspace',
}

export function DashboardHomePage() {
  const role = useRoleStore((s) => s.role)

  return (
    <div className="max-w-xl">
      <h1 className="text-xl font-semibold tracking-tight text-foreground">
        {titles[role]}
      </h1>
    </div>
  )
}
