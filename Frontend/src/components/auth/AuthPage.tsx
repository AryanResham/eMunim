import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { login, register, type AuthUser } from '@/api/auth'

const inputStyle = {
  background: 'rgba(0,0,0,0.04)',
  border: '1px solid rgba(0,0,0,0.09)',
  color: '#1A1816',
}

export function AuthPage({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = mode === 'login' ? await login(email, password) : await register(email, password, fullName)
      onAuthenticated(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="h-screen w-screen flex items-center justify-center"
      style={{ background: '#F5F2EC' }}
    >
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="w-full max-w-sm rounded-2xl px-7 py-8"
        style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.08)' }}
      >
        <div className="flex items-center gap-2.5 mb-6">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold text-sm shadow-sm"
            style={{ background: 'linear-gradient(135deg, #4B6CB7, #3454a0)' }}
          >
            eM
          </div>
          <div>
            <p className="text-sm font-semibold leading-none" style={{ color: '#1A1816' }}>eMunim</p>
            <p className="text-[10px] uppercase tracking-[0.15em] font-medium mt-0.5" style={{ color: '#A09890' }}>
              AI Ledger
            </p>
          </div>
        </div>

        <h1 className="text-lg font-semibold mb-1" style={{ color: '#1A1816' }}>
          {mode === 'login' ? 'Welcome back' : 'Create your account'}
        </h1>
        <p className="text-xs mb-5" style={{ color: '#A09890' }}>
          {mode === 'login' ? 'Sign in to continue to your workspace.' : 'Get started with AI-assisted bookkeeping.'}
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <AnimatePresence>
            {mode === 'register' && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                <label className="block text-xs font-semibold mb-1.5" style={{ color: '#78726A' }}>Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={inputStyle}
                  placeholder="Your name"
                />
              </motion.div>
            )}
          </AnimatePresence>

          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: '#78726A' }}>Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={inputStyle}
              placeholder="you@company.com"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold mb-1.5" style={{ color: '#78726A' }}>Password</label>
            <input
              type="password"
              required
              minLength={mode === 'register' ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={inputStyle}
              placeholder={mode === 'register' ? 'At least 8 characters' : '••••••••'}
            />
          </div>

          {error && <p className="text-xs" style={{ color: '#DC2626' }}>{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed transition-all"
            style={{ background: '#4B6CB7' }}
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <p className="text-xs text-center mt-5" style={{ color: '#A09890' }}>
          {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setError(null)
            }}
            className="font-semibold cursor-pointer"
            style={{ color: '#4B6CB7' }}
          >
            {mode === 'login' ? 'Sign up' : 'Sign in'}
          </button>
        </p>
      </motion.div>
    </div>
  )
}
