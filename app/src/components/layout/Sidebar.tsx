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
      className="glass-sidebar fixed left-0 top-0 h-screen z-20 flex flex-col"
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
    >
      {/* Logo */}
      <div className="flex items-center px-4 py-5 border-b border-white/8 min-h-[72px]">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold text-sm shadow-lg"
          style={{ background: 'linear-gradient(135deg, #3B6FD4, #1e4db7)' }}
        >
          eM
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.18 }}
              className="ml-3 overflow-hidden"
            >
              <p
                className="text-base font-semibold text-white leading-none"
                style={{ fontFamily: 'Calistoga, serif' }}
              >
                eMunim
              </p>
              <p className="text-[10px] uppercase tracking-[0.18em] font-medium mt-0.5"
                 style={{ color: 'rgba(240,244,255,0.45)' }}>
                AI Ledger
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navItems.map(({ icon: Icon, label, id }) => {
          const isActive = activePage === id
          return (
            <motion.button
              key={id}
              whileTap={{ scale: 0.97 }}
              className={cn(
                'relative w-full flex items-center rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 cursor-pointer',
                isActive
                  ? 'bg-white/12 text-white shadow-sm'
                  : 'text-white/50 hover:text-white/80 hover:bg-white/6'
              )}
              style={{ minHeight: 44 }}
            >
              <Icon
                size={18}
                className={cn('flex-shrink-0', isActive ? 'text-[#3B6FD4]' : '')}
              />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -6 }}
                    transition={{ duration: 0.15 }}
                    className="ml-3 whitespace-nowrap overflow-hidden"
                  >
                    {label}
                  </motion.span>
                )}
              </AnimatePresence>
              {isActive && (
                <motion.div
                  layoutId="active-indicator"
                  className="absolute right-0 w-0.5 h-6 rounded-l-full bg-[#3B6FD4]"
                />
              )}
            </motion.button>
          )
        })}
      </nav>

      {/* Bottom actions */}
      <div className="px-2 pb-4 border-t border-white/8 pt-4 space-y-1">
        <motion.button
          whileTap={{ scale: 0.97 }}
          className="w-full flex items-center rounded-xl px-3 py-2.5 text-sm font-semibold text-white transition-all duration-200 cursor-pointer"
          style={{
            background: 'linear-gradient(135deg, #3B6FD4, #2851a3)',
            boxShadow: '0 4px 16px rgba(59,111,212,0.35)',
            minHeight: 44,
          }}
        >
          <Plus size={18} className="flex-shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.15 }}
                className="ml-3 whitespace-nowrap"
              >
                New Entry
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>

        <button
          className="w-full flex items-center rounded-xl px-3 py-2.5 text-sm font-medium text-white/50 hover:text-white/80 hover:bg-white/6 transition-all cursor-pointer"
          style={{ minHeight: 44 }}
        >
          <HelpCircle size={18} className="flex-shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.15 }}
                className="ml-3 whitespace-nowrap"
              >
                Support
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        <button
          className="w-full flex items-center rounded-xl px-3 py-2.5 text-sm font-medium text-white/50 hover:text-white/80 hover:bg-white/6 transition-all cursor-pointer"
          style={{ minHeight: 44 }}
        >
          <LogOut size={18} className="flex-shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.15 }}
                className="ml-3 whitespace-nowrap"
              >
                Logout
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>

      {/* Collapse toggle */}
      <motion.button
        whileTap={{ scale: 0.93 }}
        onClick={onToggle}
        className="absolute -right-3 top-[72px] w-6 h-6 rounded-full glass flex items-center justify-center cursor-pointer z-30"
        style={{ border: '1px solid rgba(255,255,255,0.18)' }}
      >
        {collapsed
          ? <ChevronRight size={12} className="text-white/70" />
          : <ChevronLeft size={12} className="text-white/70" />
        }
      </motion.button>
    </motion.aside>
  )
}
