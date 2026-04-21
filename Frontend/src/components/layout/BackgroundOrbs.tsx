export function BackgroundOrbs() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {/* Warm beige base */}
      <div
        className="absolute inset-0"
        style={{ background: '#F5F2EC' }}
      />
      {/* Very subtle warm tint — top left */}
      <div
        className="absolute rounded-full"
        style={{
          width: 700,
          height: 700,
          top: -200,
          left: -150,
          background: 'radial-gradient(circle, rgba(180,165,140,0.18) 0%, transparent 65%)',
        }}
      />
      {/* Subtle cool tint — bottom right */}
      <div
        className="absolute rounded-full"
        style={{
          width: 500,
          height: 500,
          bottom: -120,
          right: -100,
          background: 'radial-gradient(circle, rgba(130,155,200,0.1) 0%, transparent 65%)',
        }}
      />
    </div>
  )
}
