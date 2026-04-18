import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StepIndicatorProps {
  currentStep: number
  totalSteps?: number
}

const STEP_LABELS = ['Upload', 'Classify', 'Extract', 'Validate']

export function StepIndicator({ currentStep, totalSteps = 4 }: StepIndicatorProps) {
  return (
    <div className="flex flex-col items-center gap-4 mb-8">
      {/* Step label */}
      <p className="text-xs font-semibold uppercase tracking-[0.2em]"
         style={{ color: 'rgba(240,244,255,0.45)' }}>
        Step {currentStep} of {totalSteps}
      </p>

      {/* Dots + lines */}
      <div className="flex items-center gap-0">
        {STEP_LABELS.map((label, i) => {
          const step = i + 1
          const isDone = step < currentStep
          const isActive = step === currentStep

          return (
            <div key={step} className="flex items-center">
              <div className="flex flex-col items-center gap-1.5">
                <motion.div
                  animate={{
                    scale: isActive ? 1.2 : 1,
                    backgroundColor: isDone
                      ? '#22C55E'
                      : isActive
                      ? '#3B6FD4'
                      : 'rgba(255,255,255,0.12)',
                    boxShadow: isActive
                      ? '0 0 0 3px rgba(59,111,212,0.25)'
                      : isDone
                      ? '0 0 0 3px rgba(34,197,94,0.2)'
                      : 'none',
                  }}
                  transition={{ duration: 0.25 }}
                  className="w-7 h-7 rounded-full flex items-center justify-center border"
                  style={{
                    borderColor: isDone
                      ? '#22C55E'
                      : isActive
                      ? '#3B6FD4'
                      : 'rgba(255,255,255,0.15)',
                  }}
                >
                  {isDone ? (
                    <Check size={13} className="text-white" />
                  ) : (
                    <span
                      className={cn(
                        'text-xs font-bold',
                        isActive ? 'text-white' : 'text-white/30'
                      )}
                    >
                      {step}
                    </span>
                  )}
                </motion.div>
                <span
                  className={cn(
                    'text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap',
                    isActive ? 'text-[#3B6FD4]' : isDone ? 'text-white/50' : 'text-white/25'
                  )}
                >
                  {label}
                </span>
              </div>

              {/* Connector line */}
              {i < STEP_LABELS.length - 1 && (
                <div className="w-16 h-px mx-2 mb-5 overflow-hidden rounded-full"
                     style={{ background: 'rgba(255,255,255,0.1)' }}>
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: '#3B6FD4' }}
                    animate={{ width: step < currentStep ? '100%' : '0%' }}
                    transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
