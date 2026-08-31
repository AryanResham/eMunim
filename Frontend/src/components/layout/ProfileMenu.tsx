import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Settings, LogOut } from 'lucide-react'
import type { AuthUser } from '@/api/auth'

function initials(user: AuthUser): string {
  const source = user.fullName.trim() || user.email
  const parts = source.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return source.slice(0, 2).toUpperCase()
}

export function ProfileMenu({
  user,
  onNavigate,
  onLogout,
}: {
  user: AuthUser
  onNavigate?: (page: string) => void
  onLogout: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold text-white cursor-pointer"
        style={{ background: '#4B6CB7' }}
        title={user.fullName || user.email}
      >
        {initials(user)}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 top-11 w-56 rounded-xl shadow-lg z-30 overflow-hidden"
            style={{ background: '#FBF9F5', border: '1px solid rgba(0,0,0,0.08)' }}
          >
            <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
              <p className="text-sm font-semibold truncate" style={{ color: '#1A1816' }}>
                {user.fullName || 'Your Account'}
              </p>
              <p className="text-xs truncate mt-0.5" style={{ color: '#A09890' }}>
                {user.email}
              </p>
            </div>

            <button
              onClick={() => {
                setOpen(false)
                onNavigate?.('settings')
              }}
              className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-left cursor-pointer transition-colors"
              style={{ color: '#1A1816' }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,0,0,0.03)' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
            >
              <Settings size={15} style={{ color: '#78726A' }} />
              Settings
            </button>

            <button
              onClick={() => {
                setOpen(false)
                onLogout()
              }}
              className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-left cursor-pointer transition-colors"
              style={{ color: '#1A1816', borderTop: '1px solid rgba(0,0,0,0.06)' }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,0,0,0.03)' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
            >
              <LogOut size={15} style={{ color: '#78726A' }} />
              Logout
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
