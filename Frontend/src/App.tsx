import { useEffect, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import { BackgroundOrbs } from '@/components/layout/BackgroundOrbs'
import { Sidebar } from '@/components/layout/Sidebar'
import { NotificationsBell } from '@/components/layout/NotificationsBell'
import { ProfileMenu } from '@/components/layout/ProfileMenu'
import { UploadWorkflow } from '@/components/upload/UploadWorkflow'
import { Dashboard } from '@/components/dashboard/Dashboard'
import { Records } from '@/components/records/Records'
import { Insights } from '@/components/dashboard/Insights'
import { Settings } from '@/components/settings/Settings'
import { AuthPage } from '@/components/auth/AuthPage'
import { fetchCurrentUser, logout, type AuthUser } from '@/api/auth'
import { AUTH_LOGOUT_EVENT } from '@/lib/auth'
import { motion } from 'framer-motion'

const PAGE_HEADERS: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: 'Dashboard', subtitle: 'An overview of your bookkeeping' },
  uploads: { title: 'Upload Documents', subtitle: 'Let AI handle your bookkeeping' },
  records: { title: 'Records', subtitle: 'Every document eMunim has processed' },
  insights: { title: 'Insights', subtitle: 'Vendor concentration, spend trends, and anomalies' },
  settings: { title: 'Settings', subtitle: 'Business profile and validation tuning' },
}

interface RecordsSearchSeed {
  query: string
  nonce: number
}

interface RecordsOpenSeed {
  documentId: string
  nonce: number
}

function initials(user: AuthUser): string {
  const source = user.fullName.trim() || user.email
  const parts = source.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return source.slice(0, 2).toUpperCase()
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [activePage, setActivePage] = useState('uploads')
  const [headerSearch, setHeaderSearch] = useState('')
  const [recordsSearchSeed, setRecordsSearchSeed] = useState<RecordsSearchSeed | null>(null)
  const [recordsOpenSeed, setRecordsOpenSeed] = useState<RecordsOpenSeed | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .finally(() => setAuthChecked(true))

    function handleLogout() {
      setUser(null)
      setActivePage('uploads')
    }
    window.addEventListener(AUTH_LOGOUT_EVENT, handleLogout)
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, handleLogout)
  }, [])

  const sidebarWidth = sidebarCollapsed ? 64 : 224
  const header = PAGE_HEADERS[activePage] ?? PAGE_HEADERS.uploads

  function handleHeaderSearch() {
    const query = headerSearch.trim()
    if (!query) return
    setRecordsSearchSeed({ query, nonce: Date.now() })
    setActivePage('records')
  }

  function handleOpenDocument(documentId: string) {
    setRecordsOpenSeed({ documentId, nonce: Date.now() })
    setActivePage('records')
  }

  if (!authChecked) {
    return (
      <div className="h-screen w-screen flex items-center justify-center" style={{ background: '#F5F2EC' }}>
        <Loader2 size={22} className="animate-spin" style={{ color: '#A09890' }} />
      </div>
    )
  }

  if (!user) {
    return <AuthPage onAuthenticated={setUser} />
  }

  return (
    <div className="h-screen w-screen overflow-hidden relative">
      <BackgroundOrbs />

      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((v) => !v)}
        activePage={activePage}
        onNavigate={setActivePage}
        onLogout={logout}
      />

      {/* Main content — offset by sidebar width */}
      <motion.main
        initial={{ paddingLeft: sidebarWidth }}
        animate={{ paddingLeft: sidebarWidth }}
        transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
        className="h-full flex flex-col relative z-10"
      >
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-8 py-4 border-b flex-shrink-0"
          style={{ borderColor: 'rgba(0,0,0,0.08)', background: 'rgba(245,242,236,0.8)' }}
        >
          <div>
            <h1 className="text-xl font-semibold leading-tight" style={{ color: '#1A1816' }}>
              {header.title}
            </h1>
            <p className="text-sm mt-0.5 font-normal" style={{ color: '#A09890' }}>
              {header.subtitle}
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Search */}
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
              style={{
                background: 'rgba(0,0,0,0.05)',
                border: '1px solid rgba(0,0,0,0.09)',
              }}
            >
              <Search size={14} style={{ color: '#A09890' }} />
              <input
                type="text"
                placeholder="Search records..."
                value={headerSearch}
                onChange={(e) => setHeaderSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleHeaderSearch()
                }}
                className="bg-transparent border-none outline-none text-sm w-32"
                style={{ color: '#1A1816' }}
              />
            </div>

            {/* Notifications */}
            <NotificationsBell onNavigate={setActivePage} onOpenDocument={handleOpenDocument} />

            {/* Avatar */}
            <ProfileMenu user={user} onNavigate={setActivePage} onLogout={logout} />
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto px-8 pt-8 pb-4">
          {activePage === 'dashboard' && <Dashboard />}
          {activePage === 'uploads' && <UploadWorkflow />}
          {activePage === 'records' && <Records searchSeed={recordsSearchSeed} openSeed={recordsOpenSeed} />}
          {activePage === 'insights' && <Insights onOpenDocument={handleOpenDocument} />}
          {activePage === 'settings' && <Settings />}
        </div>
      </motion.main>
    </div>
  )
}
