// TEMP — delete this component once the classifier is wired up

import { useEffect, useRef } from 'react'
import type { OCRResult } from '@/types/ocr'

interface Props {
  file: File
  result: OCRResult
  processedWidth: number
  processedHeight: number
  onContinue?: () => void
}

function confidenceColor(c: number) {
  if (c >= 0.95) return '#16a34a'   // green
  if (c >= 0.85) return '#ca8a04'   // yellow
  return '#dc2626'                   // red
}

export function OcrDebugViewer({ file, result, processedWidth, processedHeight, onContinue }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const isPdf = file.type === 'application/pdf'

  useEffect(() => {
    if (isPdf) return

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = processedWidth
    canvas.height = processedHeight

    const img = new Image()
    const url = URL.createObjectURL(file)
    img.src = url

    img.onload = () => {
      ctx.drawImage(img, 0, 0, processedWidth, processedHeight)
      URL.revokeObjectURL(url)

      for (const word of result.words) {
        const box = word.bounding_box
        ctx.strokeStyle = confidenceColor(word.confidence)
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(box[0][0], box[0][1])
        ctx.lineTo(box[1][0], box[1][1])
        ctx.lineTo(box[2][0], box[2][1])
        ctx.lineTo(box[3][0], box[3][1])
        ctx.closePath()
        ctx.stroke()
      }
    }
  }, [file, result, processedWidth, processedHeight, isPdf])

  return (
    <div style={{ display: 'flex', height: '100%', fontFamily: 'monospace', fontSize: 13 }}>

      {/* Left — canvas or PDF notice */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16, background: '#f9fafb', display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
        {isPdf ? (
          <div style={{ color: '#6b7280', marginTop: 40, textAlign: 'center' }}>
            PDF canvas preview not supported yet (Phase 4).
            <br />
            Word list on the right still shows all extracted text.
          </div>
        ) : (
          <canvas
            ref={canvasRef}
            style={{ maxWidth: '100%', maxHeight: '100%', height: 'auto', border: '1px solid #e5e7eb', background: '#fff', display: 'block' }}
          />
        )}
      </div>

      {/* Right — word list */}
      <div style={{ width: 300, flexShrink: 0, overflowY: 'auto', borderLeft: '1px solid #d1d5db', padding: '14px 12px' }}>
        <div style={{ fontWeight: 700, marginBottom: 6 }}>
          {result.words.length} words
          <span style={{ fontWeight: 400, color: '#6b7280', marginLeft: 8 }}>
            page {result.page_count}
          </span>
        </div>
        <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 10, lineHeight: 1.5 }}>
          <span style={{ color: '#16a34a' }}>■</span> ≥95% &nbsp;
          <span style={{ color: '#ca8a04' }}>■</span> ≥85% &nbsp;
          <span style={{ color: '#dc2626' }}>■</span> &lt;85%
        </div>
        {result.words.map((w, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              gap: 6,
              padding: '4px 0',
              borderBottom: '1px solid #f3f4f6',
            }}
          >
            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
              {w.text}
            </span>
            <span style={{ flexShrink: 0, fontSize: 11, color: confidenceColor(w.confidence) }}>
              {(w.confidence * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      {/* Continue button */}
      {onContinue && (
        <button
          onClick={onContinue}
          style={{
            position: 'absolute',
            bottom: 24,
            right: 24,
            padding: '10px 20px',
            background: '#1d4ed8',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          Close
        </button>
      )}
    </div>
  )
}
