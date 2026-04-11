import { useCallback, useEffect, useMemo, useState } from 'react'

const DISMISS_KEY = 'myle_pwa_install_dismiss_until_ms'
const DISMISS_DAYS = 14

export type BeforeInstallPromptLike = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

function isStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    (window.navigator as Navigator & { standalone?: boolean }).standalone ===
      true
  )
}

function getDismissUntilMs(): number {
  try {
    const raw = localStorage.getItem(DISMISS_KEY)
    if (!raw) return 0
    const n = parseInt(raw, 10)
    return Number.isFinite(n) ? n : 0
  } catch {
    return 0
  }
}

export function usePwaInstall() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptLike | null>(null)
  const [installed, setInstalled] = useState(false)
  const [dismissVersion, setDismissVersion] = useState(0)

  const standalone = useMemo(() => isStandalone(), [])

  const inDismissCooldown = useMemo(() => {
    void dismissVersion
    // Expiry is time-based; re-check when user dismisses (dismissVersion bumps).
    // eslint-disable-next-line react-hooks/purity -- need wall clock vs stored deadline
    return Date.now() < getDismissUntilMs()
  }, [dismissVersion])

  useEffect(() => {
    const onBip = (e: Event) => {
      e.preventDefault()
      setDeferred(e as BeforeInstallPromptLike)
    }
    const onInstalled = () => {
      setInstalled(true)
      setDeferred(null)
    }
    window.addEventListener('beforeinstallprompt', onBip)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onBip)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  const dismiss = useCallback(() => {
    try {
      localStorage.setItem(
        DISMISS_KEY,
        String(Date.now() + DISMISS_DAYS * 864e5),
      )
    } catch {
      /* ignore */
    }
    setDeferred(null)
    setDismissVersion((v) => v + 1)
  }, [])

  const showBanner =
    !standalone &&
    !installed &&
    !inDismissCooldown &&
    deferred !== null

  const promptInstall = useCallback(async () => {
    if (!deferred) return false
    try {
      await deferred.prompt()
      const { outcome } = await deferred.userChoice
      setDeferred(null)
      return outcome === 'accepted'
    } catch {
      setDeferred(null)
      return false
    }
  }, [deferred])

  return {
    canInstall: Boolean(deferred),
    showBanner,
    promptInstall,
    dismiss,
    standalone,
    installed,
  }
}
