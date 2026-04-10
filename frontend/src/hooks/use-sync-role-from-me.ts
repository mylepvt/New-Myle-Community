import { useEffect, useRef } from 'react'

import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import { useRoleStore } from '@/stores/role-store'
import { isRole } from '@/types/role'

/**
 * When the server session identity or role changes (login, different user), align
 * Zustand nav role with JWT. Local "preview as role" stays intact until the
 * session key (`user_id` + server role) changes.
 */
export function useSyncRoleFromMe() {
  const { data: me } = useAuthMeQuery()
  const setRole = useRoleStore((s) => s.setRole)
  const lastSessionKeyRef = useRef<string | null>(null)

  useEffect(() => {
    if (!me?.authenticated || me.user_id == null || !isRole(me.role)) {
      return
    }
    const key = `${me.user_id}:${me.role}`
    if (lastSessionKeyRef.current === key) {
      return
    }
    lastSessionKeyRef.current = key
    setRole(me.role)
  }, [me, setRole])
}
