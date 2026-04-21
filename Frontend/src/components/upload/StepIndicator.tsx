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
    <div className="flex flex-col items-center gap-3 mb-8">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em]"
         style={{ color: '#A09890' }}>
        Step {currentStep} of {totalSteps}
      </p>

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
                    scale: isActive ? 1.15 : 1,
                    backgroundColor: isDone
                      ? '#16A34A'
                      : isActive
                      ? '#4B6CB7'
                      : 'rgba(0,0,0,0.08)',
                    boxShadow: isActive
                      ? '0 0 0 3px rgba(75,108,183,0.2)'
                      : isDone
                      ? '0 0 0 3px rgba(22,163,74,0.15)'
                      : 'none',
                  }}
                  transition={{ duration: 0.22 }}
                  className="w-7 h-7 rounded-full flex items-center justify-center border"
                  style={{
                    borderColor: isDone
                      ? '#16A34A'
                      : isActive
                      ? '#4B6CB7'
                      : 'rgba(0,0,0,0.12)',
                  }}
                >
                  {isDone ? (
                    <Check size={13} className="text-white" />
                  ) : (
                    <span className={cn('text-xs font-bold', isActive ? 'text-white' : '')}
                          style={{ color: isActive ? 'white' : '#A09890' }}>
                      {step}
                    </span>
                  )}
                </motion.div>
                <span
                  className="text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap"
                  style={{
                    color: isActive ? '#4B6CB7' : isDone ? '#78726A' : '#C0B9B2',
                  }}
                >
                  {label}
                </span>
              </div>

              {i < STEP_LABELS.length - 1 && (
                <div className="w-14 h-px mx-2 mb-5 overflow-hidden rounded-full"
                     style={{ background: 'rgba(0,0,0,0.1)' }}>
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: '#4B6CB7' }}
                    animate={{ width: step < currentStep ? '100%' : '0%' }}
                    transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
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
