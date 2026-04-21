import { motion } from 'framer-motion'

export function BackgroundOrbs() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {/* Deep navy gradient base */}
      <div
        className="absolute inset-0"
        style={{
          background: 'linear-gradient(135deg, #020812 0%, #0a1628 50%, #020812 100%)',
        }}
      />

      {/* Blue orb — top left */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 600,
          height: 600,
          top: -150,
          left: -100,
          background: 'radial-gradient(circle, rgba(59, 111, 212, 0.18) 0%, transparent 70%)',
          filter: 'blur(40px)',
        }}
        animate={{ x: [0, 40, 0], y: [0, 30, 0] }}
        transition={{ duration: 12, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
      />

      {/* Teal orb — bottom right */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 500,
          height: 500,
          bottom: -100,
          right: -80,
          background: 'radial-gradient(circle, rgba(42, 191, 191, 0.12) 0%, transparent 70%)',
          filter: 'blur(40px)',
        }}
        animate={{ x: [0, -35, 0], y: [0, -25, 0] }}
        transition={{ duration: 10, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut', delay: 2 }}
      />

      {/* Subtle blue accent — center */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 300,
          height: 300,
          top: '40%',
          left: '55%',
          background: 'radial-gradient(circle, rgba(59, 111, 212, 0.08) 0%, transparent 70%)',
          filter: 'blur(60px)',
        }}
        animate={{ x: [0, 20, 0], y: [0, -20, 0] }}
        transition={{ duration: 15, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut', delay: 4 }}
      />
    </div>
  )
}
