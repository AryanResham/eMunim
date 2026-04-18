import { useState } from 'react'
import { Bell, Search } from 'lucide-react'
import { BackgroundOrbs } from '@/components/layout/BackgroundOrbs'
import { Sidebar } from '@/components/layout/Sidebar'
import { UploadWorkflow } from '@/components/upload/UploadWorkflow'
import { motion } from 'framer-motion'

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="h-screen w-screen overflow-hidden relative">
      <BackgroundOrbs />

      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((v) => !v)}
        activePage="uploads"
      />

      {/* Main content — offset by sidebar width */}
      <motion.main
        animate={{ paddingLeft: sidebarCollapsed ? 72 : 240 }}
        transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
        className="h-full flex flex-col relative z-10"
      >
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-8 py-4 border-b flex-shrink-0"
          style={{ borderColor: 'rgba(255,255,255,0.07)' }}
        >
          <div>
            <h1
              className="text-2xl font-normal text-white leading-tight"
              style={{ fontFamily: 'Calistoga, serif' }}
            >
              Upload Documents
            </h1>
            <p className="text-sm mt-0.5" style={{ color: 'rgba(240,244,255,0.45)' }}>
              Let AI handle your bookkeeping
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Search */}
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm"
              style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
              }}
            >
              <Search size={15} style={{ color: 'rgba(240,244,255,0.4)' }} />
              <input
                type="text"
                placeholder="Search records..."
                className="bg-transparent border-none outline-none text-sm w-36"
                style={{ color: 'rgba(240,244,255,0.7)' }}
              />
            </div>

            {/* Notifications */}
            <button
              className="relative w-9 h-9 rounded-xl flex items-center justify-center cursor-pointer transition-all hover:bg-white/8"
              style={{ border: '1px solid rgba(255,255,255,0.1)' }}
            >
              <Bell size={16} style={{ color: 'rgba(240,244,255,0.6)' }} />
              <span
                className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full border-2"
                style={{ background: '#EF4444', borderColor: '#020812' }}
              />
            </button>

            {/* Avatar */}
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold text-white cursor-pointer"
              style={{
                background: 'linear-gradient(135deg, #3B6FD4, #2ABFBF)',
                boxShadow: '0 2px 8px rgba(59,111,212,0.3)',
              }}
            >
              AM
            </div>
          </div>
        </header>

        {/* Upload workflow canvas */}
        <div className="flex-1 overflow-hidden px-8 pt-8 pb-4">
          <UploadWorkflow />
        </div>
      </motion.main>
    </div>
  )
}
