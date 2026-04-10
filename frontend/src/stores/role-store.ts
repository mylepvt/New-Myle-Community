import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { Role } from '@/types/role'

type RoleState = {
  role: Role
  setRole: (role: Role) => void
}

export const useRoleStore = create<RoleState>()(
  persist(
    (set) => ({
      role: 'admin',
      setRole: (role) => set({ role }),
    }),
    { name: 'myle-vl2-role' },
  ),
)
