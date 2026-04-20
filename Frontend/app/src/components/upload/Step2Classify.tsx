import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  ArrowRight,
  Store,
  CalendarDays,
  FileText,
  Image,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ClassificationResult, DocType } from '@/types/upload'
import { cn } from '@/lib/utils'

interface Step2ClassifyProps {
  file: File
  filePreviewUrl: string | null
  classification: ClassificationResult
  onProceed: (updated: ClassificationResult) => Promise<void>
  onBack: () => void
  isProcessing: boolean
}

const DOC_TYPE_LABELS: Record<DocType, string> = {
  GST_INVOICE:     'GST Invoice',
  PURCHASE_BILL:   'Purchase Bill',
  EXPENSE_RECEIPT: 'Expense',
  UTILITY_BILL:    'Utility Bill',
  CREDIT_NOTE:     'Credit Note',
  DEBIT_NOTE:      'Debit Note',
}

function ConfidenceBadge({ value }: { value: number }) {
  const color =
    value >= 90 ? '#2ABFBF' : value >= 70 ? '#F59E0B' : '#EF4444'
  const bg =
    value >= 90
      ? 'rgba(42,191,191,0.12)'
      : value >= 70
      ? 'rgba(245,158,11,0.12)'
      : 'rgba(239,68,68,0.12)'

  return (
    <span
      className="text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1.5"
      style={{ background: bg, color, border: `1px solid ${color}40` }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: color, boxShadow: `0 0 6px ${color}` }}
      />
      {value}% Confidence
    </span>
  )
}

export function Step2Classify({
  file,
  filePreviewUrl,
  classification,
  onProceed,
  onBack,
  isProcessing,
}: Step2ClassifyProps) {
  const [selectedType, setSelectedType] = useState<DocType>(classification.type)
  const [selectedSub, setSelectedSub] = useState(classification.subCategory)

  const handleProceed = () => {
    onProceed({ ...classification, type: selectedType, subCategory: selectedSub })
  }

  const isImage = file.type.startsWith('image/')

  return (
    <div className="flex flex-col gap-6 w-full max-w-4xl mx-auto">
      <div>
        <h2
          className="text-3xl font-normal text-white mb-1.5"
          style={{ fontFamily: 'Calistoga, serif' }}
        >
          Define category
        </h2>
        <p className="text-sm" style={{ color: 'rgba(240,244,255,0.55)' }}>
          Review and confirm what eMunim AI detected
        </p>
      </div>

      <div className="grid grid-cols-[2fr_3fr] gap-5">
        {/* Left: Doc preview */}
        <div
          className="glass rounded-2xl overflow-hidden flex flex-col"
          style={{ minHeight: 380 }}
        >
          <div
            className="px-4 py-3 border-b text-xs font-semibold uppercase tracking-wider"
            style={{ borderColor: 'rgba(255,255,255,0.08)', color: 'rgba(240,244,255,0.4)' }}
          >
            Document Preview
          </div>
          <div className="flex-1 flex items-center justify-center p-4">
            {isImage && filePreviewUrl ? (
              <img
                src={filePreviewUrl}
                alt="Document preview"
                className="max-h-72 max-w-full object-contain rounded-lg shadow-xl"
              />
            ) : (
              <div className="flex flex-col items-center gap-4 text-center">
                <div
                  className="w-16 h-20 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(59,111,212,0.12)', border: '1px solid rgba(59,111,212,0.2)' }}
                >
                  {isImage
                    ? <Image size={28} className="text-[#3B6FD4]" />
                    : <FileText size={28} className="text-[#3B6FD4]" />
                  }
                </div>
                <div>
                  <p className="text-sm font-medium text-white truncate max-w-[160px]">{file.name}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'rgba(240,244,255,0.4)' }}>
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Classification panel */}
        <div className="glass rounded-2xl p-5 flex flex-col gap-5">
          {/* Detected intent */}
          <div className="flex items-start justify-between gap-3">
            <div>
              <p
                className="text-[11px] font-semibold uppercase tracking-wider mb-1"
                style={{ color: 'rgba(240,244,255,0.4)' }}
              >
                Detected Intent
              </p>
              <p className="text-lg font-semibold text-white">
                {classification.label}
              </p>
            </div>
            <ConfidenceBadge value={classification.confidence} />
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-3">
            <div
              className="rounded-xl px-4 py-3"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider mb-1"
                 style={{ color: 'rgba(240,244,255,0.4)' }}>
                Transaction Date
              </p>
              <div className="flex items-center gap-2">
                <CalendarDays size={13} className="text-[#3B6FD4]" />
                <span className="text-sm font-semibold text-white">{classification.date}</span>
              </div>
            </div>
            <div
              className="rounded-xl px-4 py-3"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider mb-1"
                 style={{ color: 'rgba(240,244,255,0.4)' }}>
                Detected Merchant
              </p>
              <div className="flex items-center gap-2">
                <Store size={13} className="text-[#2ABFBF]" />
                <span className="text-sm font-semibold text-white truncate">{classification.merchant}</span>
              </div>
            </div>
          </div>

          {/* Category type selector */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider mb-2.5"
               style={{ color: 'rgba(240,244,255,0.4)' }}>
              Category Type
            </p>
            <div className="grid grid-cols-3 gap-2 p-1 rounded-xl"
                 style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.08)' }}>
              {(Object.keys(DOC_TYPE_LABELS) as DocType[]).map((type) => (
                <motion.button
                  key={type}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setSelectedType(type)}
                  className="relative py-2 px-1 rounded-lg text-xs font-semibold transition-all cursor-pointer"
                  style={{
                    color: selectedType === type ? 'white' : 'rgba(240,244,255,0.45)',
                    minHeight: 36,
                  }}
                >
                  {selectedType === type && (
                    <motion.div
                      layoutId="type-active"
                      className="absolute inset-0 rounded-lg"
                      style={{ background: 'rgba(59,111,212,0.35)', border: '1px solid rgba(59,111,212,0.5)' }}
                      transition={{ duration: 0.2 }}
                    />
                  )}
                  <span className="relative z-10">{DOC_TYPE_LABELS[type]}</span>
                </motion.button>
              ))}
            </div>
          </div>

          {/* Sub-category chips */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider mb-2.5"
               style={{ color: 'rgba(240,244,255,0.4)' }}>
              Suggested Sub-Category
            </p>
            <div className="flex flex-wrap gap-2">
              {classification.suggestedSubCategories.map((sub) => (
                <motion.button
                  key={sub}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setSelectedSub(sub)}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer',
                  )}
                  style={
                    selectedSub === sub
                      ? {
                          background: 'rgba(59,111,212,0.3)',
                          border: '1px solid rgba(59,111,212,0.6)',
                          color: 'white',
                        }
                      : {
                          background: 'rgba(255,255,255,0.06)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          color: 'rgba(240,244,255,0.6)',
                        }
                  }
                >
                  {sub}
                </motion.button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom nav */}
      <div className="flex gap-3">
        <Button
          variant="ghost"
          className="gap-2 h-11 text-white/60 hover:text-white hover:bg-white/8"
          onClick={onBack}
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
            onClick={handleProceed}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Extracting Fields...
              </>
            ) : (
              <>
                Proceed to Extraction
                <ArrowRight size={16} />
              </>
            )}
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
