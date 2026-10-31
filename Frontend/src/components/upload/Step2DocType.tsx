import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, FileText, Image, Loader2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { DocType } from '@/types/upload'

interface Step2DocTypeProps {
  file: File
  filePreviewUrl: string | null
  onProceed: (docType: DocType) => Promise<void>
  onBack: () => void
  isProcessing: boolean
}

const DOC_TYPE_LABELS: { value: DocType; label: string }[] = [
  { value: 'GST_INVOICE',     label: 'GST Invoice' },
  { value: 'PURCHASE_BILL',   label: 'Purchase Bill' },
  { value: 'EXPENSE_RECEIPT', label: 'Expense' },
  { value: 'UTILITY_BILL',    label: 'Utility Bill' },
  { value: 'CREDIT_NOTE',     label: 'Credit Note' },
  { value: 'DEBIT_NOTE',      label: 'Debit Note' },
]

export function Step2DocType({
  file,
  filePreviewUrl,
  onProceed,
  onBack,
  isProcessing,
}: Step2DocTypeProps) {
  const [selectedType, setSelectedType] = useState<DocType>('GST_INVOICE')
  const isImage = file.type.startsWith('image/')

  return (
    <div className="flex flex-col gap-5 w-full max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-semibold mb-1" style={{ color: '#1A1816' }}>
          Choose document type
        </h2>
        <p className="text-sm flex items-center gap-1.5" style={{ color: '#A09890' }}>
          <Sparkles size={14} style={{ color: '#94693D' }} />
          VLM Only mode — the vision model reads the image directly (no OCR). Pick the type so it
          extracts the right fields.
        </p>
      </div>

      <div className="grid grid-cols-[2fr_3fr] gap-4">
        {/* Left: preview */}
        <div
          className="glass rounded-2xl overflow-hidden flex flex-col"
          style={{ minHeight: 360 }}
        >
          <div className="px-4 py-2.5 border-b text-[11px] font-semibold uppercase tracking-wider" style={{ borderColor: 'rgba(0,0,0,0.07)', color: '#A09890' }}>
            Document Preview
          </div>
          <div className="flex-1 flex items-center justify-center p-4">
            {isImage && filePreviewUrl ? (
              <img
                src={filePreviewUrl}
                alt="Document preview"
                className="max-h-64 max-w-full object-contain rounded-lg shadow-sm"
              />
            ) : (
              <div className="flex flex-col items-center gap-3 text-center">
                <div
                  className="w-14 h-18 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(75,108,183,0.08)', border: '1px solid rgba(75,108,183,0.15)' }}
                >
                  {isImage ? <Image size={26} style={{ color: '#2B6CB7' }} /> : <FileText size={26} style={{ color: '#2B6CB7' }} />}
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

        {/* Right: type picker */}
        <div className="glass rounded-2xl p-5 flex flex-col gap-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: '#A09890' }}>
            Document Type
          </p>
          <div className="grid grid-cols-2 gap-2">
            {DOC_TYPE_LABELS.map((opt) => {
              const selected = selectedType === opt.value
              return (
                <motion.button
                  key={opt.value}
                  type="button"
                  whileTap={{ scale: 0.97 }}
                  onClick={() => setSelectedType(opt.value)}
                  className="rounded-xl text-left p-3 cursor-pointer"
                  style={{
                    background: selected ? 'rgba(75,108,183,0.09)' : 'rgba(0,0,0,0.03)',
                    border: selected ? '1px solid #4B6CB7' : '1px solid rgba(0,0,0,0.08)',
                  }}
                >
                  <p className="text-sm font-semibold" style={{ color: selected ? '#4B6CB7' : '#1A1816' }}>
                    {opt.label}
                  </p>
                </motion.button>
              )
            })}
          </div>

          <div
            className="rounded-xl px-4 py-3"
            style={{ background: 'rgba(148,113,61,0.08)', border: '1px solid rgba(148,113,61,0.2)' }}
          >
            <p className="text-[11px] font-semibold mb-0.5" style={{ color: '#94693D' }}>
              Note: this mode is slower (~1-4 min per document)
            </p>
            <p className="text-xs" style={{ color: '#78726A' }}>
              The on-device vision model runs on your GPU. It bypasses OCR and the LayoutLM extractor.
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
          disabled={isProcessing}
        >
          <ArrowLeft size={15} />
          Previous
        </Button>
        <motion.div whileTap={{ scale: 0.97 }} className="flex-1">
          <Button
            className="w-full gap-2 h-10 text-white text-sm font-semibold cursor-pointer"
            style={{ background: '#2B6CB7' }}
            onClick={() => onProceed(selectedType)}
            disabled={isProcessing}
          >
            {isProcessing ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Extracting with VLM...
              </>
            ) : (
              <>
                Extract with VLM
                <ArrowRight size={15} />
              </>
            )}
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
