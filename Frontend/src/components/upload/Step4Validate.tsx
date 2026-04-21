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
    <div className="flex flex-col gap-6 w-full max-w-4xl mx-auto">
      <div>
        <h2
          className="text-3xl font-normal text-white mb-1.5"
          style={{ fontFamily: 'Calistoga, serif' }}
        >
          Validate & confirm
        </h2>
        <p className="text-sm" style={{ color: 'rgba(240,244,255,0.55)' }}>
          Review extracted fields and pass validation checks before submitting
        </p>
      </div>

      <div className="grid grid-cols-[3fr_2fr] gap-5">
        {/* Left: editable fields */}
        <div
          className="glass rounded-2xl p-5 overflow-y-auto"
          style={{ maxHeight: 460 }}
        >
          <p className="text-xs font-semibold uppercase tracking-wider mb-4"
             style={{ color: 'rgba(240,244,255,0.4)' }}>
            Edit fields
          </p>
          <div className="grid grid-cols-1 gap-4">
            {fields.map((field, i) => (
              <motion.div
                key={field.key}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05, duration: 0.25 }}
              >
                <label
                  className="block text-[10px] font-semibold uppercase tracking-wider mb-1.5"
                  style={{ color: 'rgba(240,244,255,0.45)' }}
                >
                  {field.label}
                  {!field.editable && (
                    <span className="ml-2 normal-case tracking-normal text-[9px] px-1.5 py-0.5 rounded"
                          style={{ background: 'rgba(255,255,255,0.08)', color: 'rgba(240,244,255,0.35)' }}>
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
                  className="h-10 text-sm rounded-xl"
                  style={{
                    fontFamily: field.monospace ? 'JetBrains Mono, monospace' : 'Inter, sans-serif',
                    opacity: field.editable ? 1 : 0.6,
                  }}
                />
              </motion.div>
            ))}
          </div>
        </div>

        {/* Right: validation rules */}
        <div className="glass rounded-2xl p-5 flex flex-col gap-4">
          <p className="text-xs font-semibold uppercase tracking-wider"
             style={{ color: 'rgba(240,244,255,0.4)' }}>
            Validation Checks
          </p>

          <div className="flex flex-col gap-3 flex-1">
            {validationResult.rules.map((rule, i) => (
              <motion.div
                key={rule.name}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08, duration: 0.25 }}
                className="rounded-xl p-3.5"
                style={{
                  background: rule.passed ? 'rgba(34,197,94,0.07)' : 'rgba(239,68,68,0.07)',
                  border: `1px solid ${rule.passed ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
                }}
              >
                <div className="flex items-center gap-2.5 mb-1">
                  {rule.passed ? (
                    <CheckCircle2 size={15} className="text-[#22C55E] flex-shrink-0" />
                  ) : (
                    <XCircle size={15} className="text-[#EF4444] flex-shrink-0" />
                  )}
                  <p className="text-sm font-semibold text-white">{rule.name}</p>
                </div>
                <p className="text-xs ml-6" style={{ color: 'rgba(240,244,255,0.5)' }}>
                  {rule.message}
                </p>
              </motion.div>
            ))}
          </div>

          {/* Overall status */}
          <div
            className="rounded-xl p-4 text-center"
            style={{
              background: validationResult.overallPassed
                ? 'rgba(34,197,94,0.1)'
                : 'rgba(239,68,68,0.1)',
              border: `1px solid ${validationResult.overallPassed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
            }}
          >
            <p
              className="text-sm font-bold"
              style={{ color: validationResult.overallPassed ? '#22C55E' : '#EF4444' }}
            >
              {validationResult.overallPassed ? 'All checks passed' : 'Issues found'}
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'rgba(240,244,255,0.45)' }}>
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
          className="gap-2 h-11 text-white/60 hover:text-white hover:bg-white/8"
          onClick={onBack}
          disabled={isProcessing || submitted}
        >
          <ArrowLeft size={16} />
          Previous
        </Button>

        <AnimatePresence mode="wait">
          {submitted ? (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex-1 flex items-center justify-center gap-2 h-11 rounded-xl font-semibold text-sm"
              style={{ background: 'rgba(34,197,94,0.2)', border: '1px solid rgba(34,197,94,0.35)', color: '#22C55E' }}
            >
              <CheckCheck size={18} />
              Submitted to Dashboard
            </motion.div>
          ) : (
            <motion.div whileTap={{ scale: 0.97 }} className="flex-1" key="submit">
              <Button
                className="w-full gap-2 h-11 text-white font-semibold"
                style={{
                  background: validationResult.overallPassed
                    ? 'linear-gradient(135deg, #22C55E, #16a34a)'
                    : 'linear-gradient(135deg, #3B6FD4, #2851a3)',
                  boxShadow: validationResult.overallPassed
                    ? '0 4px 20px rgba(34,197,94,0.35)'
                    : '0 4px 20px rgba(59,111,212,0.4)',
                }}
                onClick={handleSubmit}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CheckCheck size={16} />
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
