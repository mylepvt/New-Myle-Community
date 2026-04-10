export type Role = 'admin' | 'leader' | 'team'

export const ROLES: Role[] = ['admin', 'leader', 'team']

export function isRole(value: string | null | undefined): value is Role {
  return value != null && (ROLES as readonly string[]).includes(value)
}
