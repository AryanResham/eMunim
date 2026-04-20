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
  if (type === 'application/pdf') return <FileText size={18} className="text-[#3B6FD4]" />
  return <Image size={18} className="text-[#2ABFBF]" />
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
    <div className="flex flex-col gap-6 w-full max-w-2xl mx-auto">
      <div>
        <h2
          className="text-3xl font-normal text-white mb-1.5"
          style={{ fontFamily: 'Calistoga, serif' }}
        >
          Upload a document
        </h2>
        <p className="text-sm" style={{ color: 'rgba(240,244,255,0.55)' }}>
          PDFs, JPEGs, and PNGs — eMunim AI will handle the rest
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className="relative rounded-2xl border-2 border-dashed p-12 flex flex-col items-center justify-center text-center cursor-pointer outline-none transition-all duration-200"
        style={{
          minHeight: 280,
          borderColor: isDragActive
            ? 'rgba(59,111,212,0.7)'
            : file
            ? 'rgba(34,197,94,0.4)'
            : 'rgba(255,255,255,0.12)',
          backgroundColor: isDragActive
            ? 'rgba(59,111,212,0.06)'
            : 'rgba(255,255,255,0.03)',
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
                className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: 'rgba(59,111,212,0.2)', boxShadow: '0 0 32px rgba(59,111,212,0.3)' }}
              >
                <CloudUpload size={28} className="text-[#3B6FD4]" />
              </div>
              <p className="text-base font-semibold text-white">Drop to upload</p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center gap-5"
            >
              <motion.div
                whileHover={{ scale: 1.05 }}
                transition={{ duration: 0.2 }}
                className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: 'rgba(42,191,191,0.12)', border: '1px solid rgba(42,191,191,0.2)' }}
              >
                <CloudUpload size={28} className="text-[#2ABFBF]" />
              </motion.div>
              <div>
                <p className="text-base font-semibold text-white mb-1">
                  Drag & drop your document here
                </p>
                <p className="text-sm" style={{ color: 'rgba(240,244,255,0.45)' }}>
                  or click to browse files
                </p>
              </div>
              <div className="flex gap-2">
                {['PDF', 'JPEG', 'PNG'].map((fmt) => (
                  <span
                    key={fmt}
                    className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full"
                    style={{
                      background: 'rgba(255,255,255,0.07)',
                      color: 'rgba(240,244,255,0.5)',
                      border: '1px solid rgba(255,255,255,0.1)',
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
              background: 'rgba(34,197,94,0.08)',
              border: '1px solid rgba(34,197,94,0.2)',
            }}
          >
            <FileIcon type={file.type} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{file.name}</p>
              <p className="text-xs" style={{ color: 'rgba(240,244,255,0.45)' }}>
                {formatBytes(file.size)}
              </p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setFile(null) }}
              className="p-1 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
            >
              <X size={14} className="text-white/50" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          variant="outline"
          className="flex-1 gap-2 h-11 border-white/15 bg-white/6 text-white/70 hover:text-white hover:bg-white/10 hover:border-white/25"
        >
          <Link size={16} />
          Connect Drive
        </Button>
        <motion.div whileTap={{ scale: 0.97 }} className={cn('flex-1', !file && 'opacity-50 pointer-events-none')}>
          <Button
            className="w-full gap-2 h-11 text-white font-semibold"
            style={{
              background: 'linear-gradient(135deg, #3B6FD4, #2851a3)',
              boxShadow: file ? '0 4px 20px rgba(59,111,212,0.4)' : 'none',
            }}
            onClick={handleContinue}
            disabled={!file || isProcessing}
          >
            {isProcessing ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Analysing...
              </>
            ) : (
              <>
                Continue
                <ArrowRight size={16} />
              </>
            )}
          </Button>
        </motion.div>
      </div>
    </div>
  )
}
