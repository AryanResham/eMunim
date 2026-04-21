import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Upload,
  FileText,
  Settings,
  Plus,
  HelpCircle,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  activePage?: string
}

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', id: 'dashboard' },
  { icon: Upload, label: 'Uploads', id: 'uploads' },
  { icon: FileText, label: 'Records', id: 'records' },
  { icon: Settings, label: 'Settings', id: 'settings' },
]

export function Sidebar({ collapsed, onToggle, activePage = 'uploads' }: SidebarProps) {
  return (
    <motion.aside
      className="glass-sidebar fixed left-0 top-0 h-screen z-20 flex flex-col overflow-hidden"
      animate={{ width: collapsed ? 64 : 224 }}
      initial={{ width: 224 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
    >
      {/* Logo + toggle */}
      <div
        className="flex items-center px-3 py-4 border-b min-h-[60px] flex-shrink-0"
        style={{ borderColor: 'rgba(0,0,0,0.08)' }}
      >
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold text-xs shadow-sm"
          style={{ background: 'linear-gradient(135deg, #4B6CB7, #3454a0)' }}
        >
          eM
        </div>

        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
              className="ml-2.5 overflow-hidden flex-1 min-w-0"
            >
              <p className="text-sm font-semibold leading-none" style={{ color: '#1A1816' }}>
                eMunim
              </p>
              <p className="text-[10px] uppercase tracking-[0.15em] font-medium mt-0.5"
                 style={{ color: '#A09890' }}>
                AI Ledger
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Toggle — always inside sidebar */}
        <motion.button
          whileTap={{ scale: 0.93 }}
          onClick={onToggle}
          className={cn(
            'w-6 h-6 rounded-md flex items-center justify-center cursor-pointer transition-colors flex-shrink-0',
            collapsed ? 'mx-auto' : 'ml-auto'
          )}
          style={{
            background: 'rgba(0,0,0,0.06)',
            border: '1px solid rgba(0,0,0,0.09)',
          }}
        >
          {collapsed
            ? <ChevronRight size={12} style={{ color: '#78726A' }} />
            : <ChevronLeft size={12} style={{ color: '#78726A' }} />
          }
        </motion.button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {navItems.map(({ icon: Icon, label, id }) => {
          const isActive = activePage === id
          return (
            <motion.button
              key={id}
              whileTap={{ scale: 0.97 }}
              className={cn(
                'relative w-full flex items-center rounded-lg px-2.5 py-2 text-sm font-medium transition-all duration-150 cursor-pointer',
                isActive
                  ? 'shadow-sm'
                  : ''
              )}
              style={{
                minHeight: 40,
                background: isActive ? 'rgba(0,0,0,0.07)' : 'transparent',
                color: isActive ? '#1A1816' : '#78726A',
              }}
              onMouseEnter={(e) => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,0,0,0.04)'
              }}
              onMouseLeave={(e) => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
              }}
            >
              <Icon
                size={17}
                className="flex-shrink-0"
                style={{ color: isActive ? '#4B6CB7' : '#78726A' }}
              />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -6 }}
                    transition={{ duration: 0.13 }}
                    className="ml-2.5 whitespace-nowrap overflow-hidden text-sm"
                  >
                    {label}
                  </motion.span>
                )}
              </AnimatePresence>
              {isActive && (
                <motion.div
                  layoutId="active-indicator"
                  className="absolute right-0 w-0.5 h-5 rounded-l-full"
                  style={{ background: '#4B6CB7' }}
                />
              )}
            </motion.button>
          )
        })}
      </nav>

      {/* Bottom actions */}
      <div
        className="px-2 pb-4 pt-3 border-t space-y-0.5 flex-shrink-0"
        style={{ borderColor: 'rgba(0,0,0,0.08)' }}
      >
        <motion.button
          whileTap={{ scale: 0.97 }}
          className="w-full flex items-center rounded-lg px-2.5 py-2 text-sm font-semibold transition-all duration-150 cursor-pointer text-white"
          style={{
            background: '#4B6CB7',
            minHeight: 40,
          }}
        >
          <Plus size={17} className="flex-shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.13 }}
                className="ml-2.5 whitespace-nowrap"
              >
                New Entry
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>

        <button
          className="w-full flex items-center rounded-lg px-2.5 py-2 text-sm font-medium transition-all cursor-pointer"
          style={{ minHeight: 40, color: '#78726A' }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,0,0,0.04)' }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
        >
          <HelpCircle size={17} className="flex-shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.13 }}
                className="ml-2.5 whitespace-nowrap"
              >
                Support
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        <button
          className="w-full flex items-center rounded-lg px-2.5 py-2 text-sm font-medium transition-all cursor-pointer"
          style={{ minHeight: 40, color: '#78726A' }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,0,0,0.04)' }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
        >
          <LogOut size={17} className="flex-shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.13 }}
                className="ml-2.5 whitespace-nowrap"
              >
                Logout
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
    </motion.aside>
  )
}
