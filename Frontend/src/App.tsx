import { useState } from 'react'
import { Bell, Search } from 'lucide-react'
import { BackgroundOrbs } from '@/components/layout/BackgroundOrbs'
import { Sidebar } from '@/components/layout/Sidebar'
import { UploadWorkflow } from '@/components/upload/UploadWorkflow'
import { motion } from 'framer-motion'

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const sidebarWidth = sidebarCollapsed ? 64 : 224

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
              Upload Documents
            </h1>
            <p className="text-sm mt-0.5 font-normal" style={{ color: '#A09890' }}>
              Let AI handle your bookkeeping
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
                className="bg-transparent border-none outline-none text-sm w-32"
                style={{ color: '#1A1816' }}
              />
            </div>

            {/* Notifications */}
            <button
              className="relative w-9 h-9 rounded-lg flex items-center justify-center cursor-pointer transition-all"
              style={{ border: '1px solid rgba(0,0,0,0.09)', background: 'rgba(0,0,0,0.04)' }}
            >
              <Bell size={15} style={{ color: '#78726A' }} />
              <span
                className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full"
                style={{ background: '#DC2626' }}
              />
            </button>

            {/* Avatar */}
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold text-white cursor-pointer"
              style={{ background: '#4B6CB7' }}
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
