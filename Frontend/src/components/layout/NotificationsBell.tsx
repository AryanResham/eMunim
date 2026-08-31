import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Bell, Info } from 'lucide-react'
import { fetchNotifications, type AppNotification } from '@/api/backend'

export function NotificationsBell({
  onNavigate,
  onOpenDocument,
}: {
  onNavigate?: (page: string) => void
  onOpenDocument?: (documentId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [loaded, setLoaded] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    fetchNotifications()
      .then((n) => !cancelled && setNotifications(n))
      .catch(() => {})
      .finally(() => !cancelled && setLoaded(true))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const hasAlerts = notifications.length > 0

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative w-9 h-9 rounded-lg flex items-center justify-center cursor-pointer transition-all"
        style={{ border: '1px solid rgba(0,0,0,0.09)', background: 'rgba(0,0,0,0.04)' }}
      >
        <Bell size={15} style={{ color: '#78726A' }} />
        {loaded && hasAlerts && (
          <span
            className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full"
            style={{ background: '#DC2626' }}
          />
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 top-11 w-80 rounded-xl shadow-lg z-30 overflow-hidden"
            style={{ background: '#FBF9F5', border: '1px solid rgba(0,0,0,0.08)' }}
          >
            <p
              className="text-[11px] font-semibold uppercase tracking-wider px-4 pt-3 pb-2"
              style={{ color: '#A09890' }}
            >
              Needs Attention
            </p>
            <div className="max-h-80 overflow-y-auto">
              {!loaded ? (
                <p className="text-sm px-4 py-4" style={{ color: '#A09890' }}>
                  Loading…
                </p>
              ) : !hasAlerts ? (
                <div className="flex items-center gap-2 px-4 py-4">
                  <Info size={14} style={{ color: '#A09890' }} />
                  <p className="text-sm" style={{ color: '#78726A' }}>
                    Nothing needs your attention right now.
                  </p>
                </div>
              ) : (
                notifications.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => {
                      setOpen(false)
                      if (n.documentId) {
                        onOpenDocument?.(n.documentId)
                      } else {
                        onNavigate?.('insights')
                      }
                    }}
                    className="w-full text-left flex items-start gap-2.5 px-4 py-2.5 cursor-pointer transition-colors"
                    style={{ borderTop: '1px solid rgba(0,0,0,0.05)' }}
                    onMouseEnter={(e) => {
                      ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,0,0,0.03)'
                    }}
                    onMouseLeave={(e) => {
                      ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                    }}
                  >
                    <AlertTriangle
                      size={14}
                      className="flex-shrink-0 mt-0.5"
                      style={{ color: n.severity === 'error' ? '#DC2626' : '#B45309' }}
                    />
                    <p className="text-sm leading-snug" style={{ color: '#1A1816' }}>
                      {n.message}
                    </p>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
