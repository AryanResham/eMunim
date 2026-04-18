import { motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, CheckCircle, AlertCircle, Loader2, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import type { ClassificationResult, ExtractedField } from '@/types/upload'

interface Step3ExtractProps {
  file: File
  filePreviewUrl: string | null
  classification: ClassificationResult
  fields: ExtractedField[]
  onProceed: () => Promise<void>
  onBack: () => void
  isProcessing: boolean
}

function FieldCard({ field, index }: { field: ExtractedField; index: number }) {
  const isHighConfidence = field.confidence >= 85

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="rounded-xl p-3.5 flex items-center gap-4"
      style={{
        background: 'rgba(255,255,255,0.05)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div className="flex-1 min-w-0">
        <p
          className="text-[10px] font-semibold uppercase tracking-wider mb-1"
          style={{ color: 'rgba(240,244,255,0.4)' }}
        >
          {field.label}
        </p>
        <p
          className="text-sm font-semibold text-white truncate"
          style={{ fontFamily: field.monospace ? 'JetBrains Mono, monospace' : 'inherit' }}
        >
          {field.value}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <Progress
            value={field.confidence}
            className="h-1 flex-1"
            style={{ background: 'rgba(255,255,255,0.1)' }}
          />
          <span
            className="text-[10px] font-mono font-semibold w-8 text-right"
            style={{ color: 'rgba(240,244,255,0.45)' }}
          >
            {field.confidence}%
          </span>
        </div>
      </div>
      {isHighConfidence ? (
        <CheckCircle size={16} className="text-[#22C55E] flex-shrink-0" />
      ) : (
        <AlertCircle size={16} className="text-[#F59E0B] flex-shrink-0" />
      )}
    </motion.div>
  )
}

function SkeletonField({ index }: { index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.06 }}
      className="rounded-xl p-3.5 animate-pulse"
      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}
    >
      <div className="h-2.5 w-20 rounded mb-2" style={{ background: 'rgba(255,255,255,0.08)' }} />
      <div className="h-4 w-32 rounded mb-2" style={{ background: 'rgba(255,255,255,0.1)' }} />
      <div className="h-1 w-full rounded" style={{ background: 'rgba(255,255,255,0.06)' }} />
    </motion.div>
  )
}

export function Step3Extract({
  file,
  filePreviewUrl,
  classification,
  fields,
  onProceed,
  onBack,
  isProcessing,
}: Step3ExtractProps) {
  const isImage = file.type.startsWith('image/')
  const showSkeleton = fields.length === 0

  return (
    <div className="flex flex-col gap-6 w-full max-w-4xl mx-auto">
      <div>
        <h2
          className="text-3xl font-normal text-white mb-1.5"
          style={{ fontFamily: 'Calistoga, serif' }}
        >
          Extracted fields
        </h2>
        <p className="text-sm" style={{ color: 'rgba(240,244,255,0.55)' }}>
          AI extracted the following data from your {classification.label.toLowerCase()}
        </p>
      </div>

      <div className="grid grid-cols-[1fr_2fr] gap-5">
        {/* Left: mini doc preview */}
        <div
          className="glass rounded-2xl overflow-hidden flex flex-col"
          style={{ maxHeight: 480 }}
        >
          <div
            className="px-4 py-3 border-b text-xs font-semibold uppercase tracking-wider"
            style={{ borderColor: 'rgba(255,255,255,0.08)', color: 'rgba(240,244,255,0.4)' }}
          >
            Source
          </div>
          <div className="flex-1 flex items-center justify-center p-4">
            {isImage && filePreviewUrl ? (
              <img
                src={filePreviewUrl}
                alt="Document"
                className="max-h-64 max-w-full object-contain rounded-lg opacity-80"
              />
            ) : (
              <div className="flex flex-col items-center gap-3 text-center">
                <div
                  className="w-14 h-16 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(59,111,212,0.12)', border: '1px solid rgba(59,111,212,0.2)' }}
                >
                  <FileText size={24} className="text-[#3B6FD4]" />
                </div>
                <p className="text-xs font-medium text-white/70 truncate max-w-[140px]">{file.name}</p>
              </div>
            )}
          </div>

          {/* Classification badge */}
          <div
            className="px-4 py-3 border-t"
            style={{ borderColor: 'rgba(255,255,255,0.08)' }}
          >
            <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'rgba(240,244,255,0.4)' }}>
              Classified as
            </p>
            <p className="text-sm font-semibold text-white">{classification.label}</p>
            <p className="text-xs" style={{ color: 'rgba(240,244,255,0.5)' }}>{classification.subCategory}</p>
          </div>
        </div>

        {/* Right: fields */}
        <div
          className="glass rounded-2xl p-4 overflow-y-auto"
          style={{ maxHeight: 480 }}
        >
          <div className="grid grid-cols-1 gap-3">
            {showSkeleton
              ? Array.from({ length: 6 }).map((_, i) => <SkeletonField key={i} index={i} />)
              : fields.map((f, i) => <FieldCard key={f.key} field={f} index={i} />)
            }
          </div>
        </div>
      </div>

      {/* Bottom nav */}
      <div className="flex gap-3">
        <Button
          variant="ghost"
          className="gap-2 h-11 text-white/60 hover:text-white hover:bg-white/8"
          onClick={onBack}
          disabled={isProcessing}
        >
          <ArrowLeft size={16} />
          Previous
        </Button>
        <motion.div whileTap={{ scale: 0.97 }} className="flex-1">
          <Button
            className="w-full gap-2 h-11 text-white font-semibold"
            style={{
              background: 'linear-gradient(135deg, #3B6FD4, #2851a3)',
              boxShadow: '0 4px 20px rgba(59,111,212,0.4)',
            }}
            onClick={onProceed}
            disabled={isProcessing || showSkeleton}
          >
            {isProcessing ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Running Validation...
              </>
            ) : (
              <>
                Proceed to Validation
                <ArrowRight size={16} />
              </>
            )}
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
