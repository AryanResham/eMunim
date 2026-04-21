import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, CheckCircle2, XCircle, CheckCheck, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { ExtractedField, ValidationResult } from '@/types/upload'

interface Step4ValidateProps {
  fields: ExtractedField[]
  validationResult: ValidationResult
  onSubmit: () => void
  onBack: () => void
  isProcessing: boolean
}

export function Step4Validate({
  fields,
  validationResult,
  onSubmit,
  onBack,
  isProcessing,
}: Step4ValidateProps) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((f) => [f.key, f.value]))
  )
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = async () => {
    setSubmitted(true)
    await new Promise((r) => setTimeout(r, 600))
    onSubmit()
  }

  return (
    <div className="flex flex-col gap-5 w-full max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-semibold mb-1" style={{ color: '#1A1816' }}>
          Validate & confirm
        </h2>
        <p className="text-sm" style={{ color: '#A09890' }}>
          Review extracted fields and pass validation checks before submitting
        </p>
      </div>

      <div className="grid grid-cols-[3fr_2fr] gap-4">
        {/* Left: editable fields */}
        <div className="glass rounded-2xl p-5 overflow-y-auto" style={{ maxHeight: 440 }}>
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-4" style={{ color: '#A09890' }}>
            Edit fields
          </p>
          <div className="grid grid-cols-1 gap-4">
            {fields.map((field, i) => (
              <motion.div
                key={field.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04, duration: 0.22 }}
              >
                <label
                  className="block text-[10px] font-semibold uppercase tracking-wider mb-1.5"
                  style={{ color: '#A09890' }}
                >
                  {field.label}
                  {!field.editable && (
                    <span className="ml-2 normal-case tracking-normal text-[9px] px-1.5 py-0.5 rounded"
                          style={{ background: 'rgba(0,0,0,0.06)', color: '#A09890' }}>
                      read-only
                    </span>
                  )}
                </label>
                <Input
                  value={values[field.key] ?? ''}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [field.key]: e.target.value }))
                  }
                  disabled={!field.editable}
                  className="h-9 text-sm rounded-lg"
                  style={{
                    fontFamily: field.monospace ? 'JetBrains Mono, monospace' : 'Inter, sans-serif',
                    opacity: field.editable ? 1 : 0.55,
                    border: '1px solid rgba(0,0,0,0.12)',
                    background: field.editable ? 'white' : 'rgba(0,0,0,0.03)',
                    color: '#1A1816',
                  }}
                />
              </motion.div>
            ))}
          </div>
        </div>

        {/* Right: validation rules */}
        <div className="glass rounded-2xl p-5 flex flex-col gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: '#A09890' }}>
            Validation Checks
          </p>

          <div className="flex flex-col gap-2.5 flex-1">
            {validationResult.rules.map((rule, i) => (
              <motion.div
                key={rule.name}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.07, duration: 0.22 }}
                className="rounded-xl p-3"
                style={{
                  background: rule.passed ? 'rgba(22,163,74,0.06)' : 'rgba(220,38,38,0.06)',
                  border: `1px solid ${rule.passed ? 'rgba(22,163,74,0.18)' : 'rgba(220,38,38,0.18)'}`,
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  {rule.passed ? (
                    <CheckCircle2 size={14} style={{ color: '#16A34A', flexShrink: 0 }} />
                  ) : (
                    <XCircle size={14} style={{ color: '#DC2626', flexShrink: 0 }} />
                  )}
                  <p className="text-sm font-semibold" style={{ color: '#1A1816' }}>{rule.name}</p>
                </div>
                <p className="text-xs ml-5" style={{ color: '#78726A' }}>
                  {rule.message}
                </p>
              </motion.div>
            ))}
          </div>

          {/* Overall status */}
          <div
            className="rounded-xl p-4 text-center"
            style={{
              background: validationResult.overallPassed ? 'rgba(22,163,74,0.08)' : 'rgba(220,38,38,0.08)',
              border: `1px solid ${validationResult.overallPassed ? 'rgba(22,163,74,0.2)' : 'rgba(220,38,38,0.2)'}`,
            }}
          >
            <p
              className="text-sm font-bold"
              style={{ color: validationResult.overallPassed ? '#16A34A' : '#DC2626' }}
            >
              {validationResult.overallPassed ? 'All checks passed' : 'Issues found'}
            </p>
            <p className="text-xs mt-0.5" style={{ color: '#78726A' }}>
              {validationResult.overallPassed
                ? 'Ready to submit to dashboard'
                : 'Review and fix before submitting'}
            </p>
          </div>
        </div>
      </div>

      {/* Bottom nav */}
      <div className="flex gap-3">
        <Button
          variant="ghost"
          className="gap-2 h-10 text-sm cursor-pointer"
          style={{ color: '#78726A' }}
          onClick={onBack}
          disabled={isProcessing || submitted}
        >
          <ArrowLeft size={15} />
          Previous
        </Button>

        <AnimatePresence mode="wait">
          {submitted ? (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex-1 flex items-center justify-center gap-2 h-10 rounded-xl font-semibold text-sm"
              style={{ background: 'rgba(22,163,74,0.12)', border: '1px solid rgba(22,163,74,0.25)', color: '#16A34A' }}
            >
              <CheckCheck size={16} />
              Submitted to Dashboard
            </motion.div>
          ) : (
            <motion.div whileTap={{ scale: 0.97 }} className="flex-1" key="submit">
              <Button
                className="w-full gap-2 h-10 text-white text-sm font-semibold cursor-pointer"
                style={{
                  background: validationResult.overallPassed ? '#16A34A' : '#4B6CB7',
                }}
                onClick={handleSubmit}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CheckCheck size={15} />
                    {validationResult.overallPassed ? 'Submit to Dashboard' : 'Submit Anyway'}
                  </>
                )}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
