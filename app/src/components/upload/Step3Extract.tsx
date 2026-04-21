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
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="rounded-xl p-3.5 flex items-center gap-4"
      style={{
        background: 'rgba(0,0,0,0.03)',
        border: '1px solid rgba(0,0,0,0.07)',
      }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-wider mb-1" style={{ color: '#A09890' }}>
          {field.label}
        </p>
        <p
          className="text-sm font-semibold truncate"
          style={{
            color: '#1A1816',
            fontFamily: field.monospace ? 'JetBrains Mono, monospace' : 'inherit',
          }}
        >
          {field.value}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <Progress
            value={field.confidence}
            className="h-1 flex-1"
            style={{ background: 'rgba(0,0,0,0.08)' }}
          />
          <span className="text-[10px] font-mono font-semibold w-8 text-right" style={{ color: '#A09890' }}>
            {field.confidence}%
          </span>
        </div>
      </div>
      {isHighConfidence ? (
        <CheckCircle size={15} style={{ color: '#16A34A', flexShrink: 0 }} />
      ) : (
        <AlertCircle size={15} style={{ color: '#D97706', flexShrink: 0 }} />
      )}
    </motion.div>
  )
}

function SkeletonField({ index }: { index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.05 }}
      className="rounded-xl p-3.5 animate-pulse"
      style={{ background: 'rgba(0,0,0,0.04)', border: '1px solid rgba(0,0,0,0.06)' }}
    >
      <div className="h-2 w-20 rounded mb-2" style={{ background: 'rgba(0,0,0,0.08)' }} />
      <div className="h-3.5 w-28 rounded mb-2" style={{ background: 'rgba(0,0,0,0.1)' }} />
      <div className="h-1 w-full rounded" style={{ background: 'rgba(0,0,0,0.06)' }} />
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
    <div className="flex flex-col gap-5 w-full max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-semibold mb-1" style={{ color: '#1A1816' }}>
          Extracted fields
        </h2>
        <p className="text-sm" style={{ color: '#A09890' }}>
          AI extracted the following data from your {classification.label.toLowerCase()}
        </p>
      </div>

      <div className="grid grid-cols-[1fr_2fr] gap-4">
        {/* Left: mini doc preview */}
        <div className="glass rounded-2xl overflow-hidden flex flex-col" style={{ maxHeight: 460 }}>
          <div
            className="px-4 py-2.5 border-b text-[11px] font-semibold uppercase tracking-wider"
            style={{ borderColor: 'rgba(0,0,0,0.07)', color: '#A09890' }}
          >
            Source
          </div>
          <div className="flex-1 flex items-center justify-center p-4">
            {isImage && filePreviewUrl ? (
              <img
                src={filePreviewUrl}
                alt="Document"
                className="max-h-56 max-w-full object-contain rounded-lg"
                style={{ opacity: 0.9 }}
              />
            ) : (
              <div className="flex flex-col items-center gap-3 text-center">
                <div
                  className="w-12 h-14 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(75,108,183,0.08)', border: '1px solid rgba(75,108,183,0.15)' }}
                >
                  <FileText size={22} style={{ color: '#4B6CB7' }} />
                </div>
                <p className="text-xs font-medium truncate max-w-[130px]" style={{ color: '#78726A' }}>{file.name}</p>
              </div>
            )}
          </div>

          {/* Classification badge */}
          <div className="px-4 py-3 border-t" style={{ borderColor: 'rgba(0,0,0,0.07)' }}>
            <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: '#A09890' }}>
              Classified as
            </p>
            <p className="text-sm font-semibold" style={{ color: '#1A1816' }}>{classification.label}</p>
            <p className="text-xs" style={{ color: '#78726A' }}>{classification.subCategory}</p>
          </div>
        </div>

        {/* Right: fields */}
        <div className="glass rounded-2xl p-4 overflow-y-auto" style={{ maxHeight: 460 }}>
          <div className="grid grid-cols-1 gap-2.5">
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
          className="gap-2 h-10 text-sm cursor-pointer"
          style={{ color: '#78726A' }}
          onClick={onBack}
          disabled={isProcessing}
        >
          <ArrowLeft size={15} />
          Previous
        </Button>
        <motion.div whileTap={{ scale: 0.97 }} className="flex-1">
          <Button
            className="w-full gap-2 h-10 text-white text-sm font-semibold cursor-pointer"
            style={{ background: '#4B6CB7' }}
            onClick={onProceed}
            disabled={isProcessing || showSkeleton}
          >
            {isProcessing ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Running Validation...
              </>
            ) : (
              <>
                Proceed to Validation
                <ArrowRight size={15} />
              </>
            )}
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
