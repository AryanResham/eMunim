import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { CloudUpload, FileText, Image, X, Link, ArrowRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Step1UploadProps {
  onFileReady: (file: File) => Promise<void>
  isProcessing: boolean
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function FileIcon({ type }: { type: string }) {
  if (type === 'application/pdf') return <FileText size={18} style={{ color: '#4B6CB7' }} />
  return <Image size={18} style={{ color: '#4B6CB7' }} />
}

export function Step1Upload({ onFileReady, isProcessing }: Step1UploadProps) {
  const [file, setFile] = useState<File | null>(null)

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    multiple: false,
  })

  const handleContinue = async () => {
    if (!file) return
    await onFileReady(file)
  }

  return (
    <div className="flex flex-col gap-5 w-full max-w-2xl mx-auto">
      <div>
        <h2 className="text-2xl font-semibold mb-1" style={{ color: '#1A1816' }}>
          Upload a document
        </h2>
        <p className="text-sm" style={{ color: '#A09890' }}>
          PDFs, JPEGs, and PNGs — eMunim AI will handle the rest
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className="relative rounded-2xl border-2 border-dashed p-12 flex flex-col items-center justify-center text-center cursor-pointer outline-none transition-all duration-200"
        style={{
          minHeight: 260,
          borderColor: isDragActive
            ? '#4B6CB7'
            : file
            ? '#16A34A'
            : 'rgba(0,0,0,0.14)',
          backgroundColor: isDragActive
            ? 'rgba(75,108,183,0.05)'
            : file
            ? 'rgba(22,163,74,0.03)'
            : 'rgba(0,0,0,0.02)',
        }}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {isDragActive ? (
            <motion.div
              key="drag"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center gap-4"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center"
                style={{ background: 'rgba(75,108,183,0.12)' }}
              >
                <CloudUpload size={26} style={{ color: '#4B6CB7' }} />
              </div>
              <p className="text-base font-semibold" style={{ color: '#1A1816' }}>Drop to upload</p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center gap-4"
            >
              <motion.div
                whileHover={{ scale: 1.04 }}
                transition={{ duration: 0.18 }}
                className="w-14 h-14 rounded-xl flex items-center justify-center"
                style={{ background: 'rgba(0,0,0,0.06)', border: '1px solid rgba(0,0,0,0.09)' }}
              >
                <CloudUpload size={26} style={{ color: '#78726A' }} />
              </motion.div>
              <div>
                <p className="text-base font-semibold mb-1" style={{ color: '#1A1816' }}>
                  Drag & drop your document here
                </p>
                <p className="text-sm" style={{ color: '#A09890' }}>
                  or click to browse files
                </p>
              </div>
              <div className="flex gap-2">
                {['PDF', 'JPEG', 'PNG'].map((fmt) => (
                  <span
                    key={fmt}
                    className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full"
                    style={{
                      background: 'rgba(0,0,0,0.06)',
                      color: '#A09890',
                      border: '1px solid rgba(0,0,0,0.1)',
                    }}
                  >
                    {fmt}
                  </span>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Selected file chip */}
      <AnimatePresence>
        {file && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="flex items-center gap-3 px-4 py-3 rounded-xl"
            style={{
              background: 'rgba(22,163,74,0.07)',
              border: '1px solid rgba(22,163,74,0.2)',
            }}
          >
            <FileIcon type={file.type} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" style={{ color: '#1A1816' }}>{file.name}</p>
              <p className="text-xs" style={{ color: '#A09890' }}>
                {formatBytes(file.size)}
              </p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setFile(null) }}
              className="p-1 rounded-lg transition-colors cursor-pointer"
              style={{ color: '#A09890' }}
            >
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          variant="outline"
          className="flex-1 gap-2 h-10 text-sm cursor-pointer"
          style={{
            border: '1px solid rgba(0,0,0,0.12)',
            background: 'rgba(0,0,0,0.04)',
            color: '#78726A',
          }}
        >
          <Link size={15} />
          Connect Drive
        </Button>
        <motion.div whileTap={{ scale: 0.97 }} className={cn('flex-1', !file && 'opacity-40 pointer-events-none')}>
          <Button
            className="w-full gap-2 h-10 text-white text-sm font-semibold cursor-pointer"
            style={{ background: '#4B6CB7' }}
            onClick={handleContinue}
            disabled={!file || isProcessing}
          >
            {isProcessing ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Analysing...
              </>
            ) : (
              <>
                Continue
                <ArrowRight size={15} />
              </>
            )}
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
