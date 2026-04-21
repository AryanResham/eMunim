import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  ArrowRight,
  Store,
  CalendarDays,
  FileText,
  Image,
  Loader2,
  ScanText,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ClassificationResult, DocType } from '@/types/upload'
import type { OCRResult } from '@/types/ocr'
import { OcrDebugViewer } from '@/components/OcrDebugViewer'
import { cn } from '@/lib/utils'

interface Step2ClassifyProps {
  file: File
  filePreviewUrl: string | null
  classification: ClassificationResult
  ocrResult: OCRResult | null
  processedWidth: number
  processedHeight: number
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
    value >= 90 ? '#16A34A' : value >= 70 ? '#D97706' : '#DC2626'
  const bg =
    value >= 90
      ? 'rgba(22,163,74,0.1)'
      : value >= 70
      ? 'rgba(217,119,6,0.1)'
      : 'rgba(220,38,38,0.1)'

  return (
    <span
      className="text-xs font-semibold px-3 py-1 rounded-full flex items-center gap-1.5"
      style={{ background: bg, color, border: `1px solid ${color}30` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {value}% Confidence
    </span>
  )
}

export function Step2Classify({
  file,
  filePreviewUrl,
  classification,
  ocrResult,
  processedWidth,
  processedHeight,
  onProceed,
  onBack,
  isProcessing,
}: Step2ClassifyProps) {
  const [selectedType, setSelectedType] = useState<DocType>(classification.type)
  const [selectedSub, setSelectedSub] = useState(classification.subCategory)
  const [showOcr, setShowOcr] = useState(false)

  const handleProceed = () => {
    onProceed({ ...classification, type: selectedType, subCategory: selectedSub })
  }

  const isImage = file.type.startsWith('image/')

  return (
    <div className="flex flex-col gap-5 w-full max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-semibold mb-1" style={{ color: '#1A1816' }}>
          Define category
        </h2>
        <p className="text-sm" style={{ color: '#A09890' }}>
          Review and confirm what eMunim AI detected
        </p>
      </div>

      <div className="grid grid-cols-[2fr_3fr] gap-4">
        {/* Left: Doc preview */}
        <div
          className="glass rounded-2xl overflow-hidden flex flex-col"
          style={{ minHeight: 360 }}
        >
          <div
            className="px-4 py-2.5 border-b flex items-center justify-between"
            style={{ borderColor: 'rgba(0,0,0,0.07)' }}
          >
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: '#A09890' }}>
              Document Preview
            </span>
            {ocrResult && (
              <button
                onClick={() => setShowOcr(true)}
                className="flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                style={{
                  background: 'rgba(75,108,183,0.1)',
                  border: '1px solid rgba(75,108,183,0.25)',
                  color: '#4B6CB7',
                }}
              >
                <ScanText size={12} />
                View OCR
              </button>
            )}
          </div>
          <div className="flex-1 flex items-center justify-center p-4">
            {isImage && filePreviewUrl ? (
              <img
                src={filePreviewUrl}
                alt="Document preview"
                className="max-h-64 max-w-full object-contain rounded-lg shadow-sm"
              />
            ) : (
              <div className="flex flex-col items-center gap-4 text-center">
                <div
                  className="w-14 h-18 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(75,108,183,0.08)', border: '1px solid rgba(75,108,183,0.15)' }}
                >
                  {isImage
                    ? <Image size={26} style={{ color: '#4B6CB7' }} />
                    : <FileText size={26} style={{ color: '#4B6CB7' }} />
                  }
                </div>
                <div>
                  <p className="text-sm font-medium truncate max-w-[150px]" style={{ color: '#1A1816' }}>{file.name}</p>
                  <p className="text-xs mt-0.5" style={{ color: '#A09890' }}>
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Classification panel */}
        <div className="glass rounded-2xl p-5 flex flex-col gap-4">
          {/* Detected intent */}
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: '#A09890' }}>
                Detected Intent
              </p>
              <p className="text-lg font-semibold" style={{ color: '#1A1816' }}>
                {classification.label}
              </p>
            </div>
            <ConfidenceBadge value={classification.confidence} />
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-3">
            <div
              className="rounded-xl px-4 py-3"
              style={{ background: 'rgba(0,0,0,0.04)', border: '1px solid rgba(0,0,0,0.07)' }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider mb-1" style={{ color: '#A09890' }}>
                Transaction Date
              </p>
              <div className="flex items-center gap-2">
                <CalendarDays size={13} style={{ color: '#4B6CB7' }} />
                <span className="text-sm font-semibold" style={{ color: '#1A1816' }}>{classification.date}</span>
              </div>
            </div>
            <div
              className="rounded-xl px-4 py-3"
              style={{ background: 'rgba(0,0,0,0.04)', border: '1px solid rgba(0,0,0,0.07)' }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider mb-1" style={{ color: '#A09890' }}>
                Detected Merchant
              </p>
              <div className="flex items-center gap-2">
                <Store size={13} style={{ color: '#4B6CB7' }} />
                <span className="text-sm font-semibold truncate" style={{ color: '#1A1816' }}>{classification.merchant}</span>
              </div>
            </div>
          </div>

          {/* Category type selector */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: '#A09890' }}>
              Category Type
            </p>
            <div className="grid grid-cols-4 gap-1.5 p-1 rounded-xl"
                 style={{ background: 'rgba(0,0,0,0.05)', border: '1px solid rgba(0,0,0,0.08)' }}>
              {(Object.keys(DOC_TYPE_LABELS) as DocType[]).map((type) => (
                <motion.button
                  key={type}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setSelectedType(type)}
                  className="relative py-1.5 px-1 rounded-lg text-xs font-semibold transition-all cursor-pointer"
                  style={{
                    color: selectedType === type ? '#1A1816' : '#A09890',
                    minHeight: 32,
                  }}
                >
                  {selectedType === type && (
                    <motion.div
                      layoutId="type-active"
                      className="absolute inset-0 rounded-lg"
                      style={{ background: 'white', border: '1px solid rgba(0,0,0,0.1)', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}
                      transition={{ duration: 0.18 }}
                    />
                  )}
                  <span className="relative z-10">{DOC_TYPE_LABELS[type]}</span>
                </motion.button>
              ))}
            </div>
          </div>

          {/* Sub-category chips */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: '#A09890' }}>
              Suggested Sub-Category
            </p>
            <div className="flex flex-wrap gap-2">
              {classification.suggestedSubCategories.map((sub) => (
                <motion.button
                  key={sub}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setSelectedSub(sub)}
                  className={cn('px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer')}
                  style={
                    selectedSub === sub
                      ? {
                          background: 'rgba(75,108,183,0.12)',
                          border: '1px solid rgba(75,108,183,0.35)',
                          color: '#4B6CB7',
                        }
                      : {
                          background: 'rgba(0,0,0,0.05)',
                          border: '1px solid rgba(0,0,0,0.09)',
                          color: '#78726A',
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

      {/* OCR overlay */}
      <AnimatePresence>
        {showOcr && ocrResult && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50"
            style={{ background: 'rgba(0,0,0,0.55)' }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.97 }}
              transition={{ duration: 0.18 }}
              className="absolute inset-4 rounded-2xl overflow-hidden"
              style={{ background: '#fff', boxShadow: '0 24px 80px rgba(0,0,0,0.25)' }}
            >
              <button
                onClick={() => setShowOcr(false)}
                className="absolute top-3 right-3 z-10 p-2 rounded-lg cursor-pointer transition-colors"
                style={{ background: 'rgba(0,0,0,0.07)', color: '#78726A' }}
              >
                <X size={16} />
              </button>
              <OcrDebugViewer
                file={file}
                result={ocrResult}
                processedWidth={processedWidth}
                processedHeight={processedHeight}
                onContinue={() => setShowOcr(false)}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom nav */}
      <div className="flex gap-3">
        <Button
          variant="ghost"
          className="gap-2 h-10 text-sm cursor-pointer"
          style={{ color: '#78726A' }}
          onClick={onBack}
        >
          <ArrowLeft size={15} />
          Previous
        </Button>
        <motion.div whileTap={{ scale: 0.97 }} className="flex-1">
          <Button
            className="w-full gap-2 h-10 text-white text-sm font-semibold cursor-pointer"
            style={{ background: '#4B6CB7' }}
            onClick={handleProceed}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Extracting Fields...
              </>
            ) : (
              <>
                Proceed to Extraction
                <ArrowRight size={15} />
              </>
            )}
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
