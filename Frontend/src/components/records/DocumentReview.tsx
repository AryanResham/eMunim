import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { X, Loader2, FileText, Check, RotateCcw, ArrowDownToLine, ArrowUpFromLine } from 'lucide-react'
import {
  fetchDocumentDetail,
  fetchDocumentFileUrl,
  updateDocumentFields,
  type DocumentDetail,
  type DocumentDirection,
} from '@/api/backend'
import type { DocType } from '@/types/upload'

const DOC_TYPE_LABELS: Record<DocType, string> = {
  GST_INVOICE: 'GST Tax Invoice',
  PURCHASE_BILL: 'Purchase Bill',
  EXPENSE_RECEIPT: 'Expense Receipt',
  UTILITY_BILL: 'Utility Bill',
  CREDIT_NOTE: 'Credit Note',
  DEBIT_NOTE: 'Debit Note',
}

function StatusBadge({ passed }: { passed: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0"
      style={{
        background: passed ? 'rgba(46,125,50,0.1)' : 'rgba(220,38,38,0.1)',
        color: passed ? '#2E7D32' : '#DC2626',
      }}
    >
      {passed ? 'Passed' : 'Needs Review'}
    </span>
  )
}

function confidenceTier(confidence: number): { color: string; bg: string; label: string } {
  if (confidence >= 85) return { color: '#2E7D32', bg: 'rgba(46,125,50,0.08)', label: 'Auto-accepted' }
  if (confidence >= 60) return { color: '#B45309', bg: 'rgba(180,83,9,0.08)', label: 'Review recommended' }
  return { color: '#DC2626', bg: 'rgba(220,38,38,0.08)', label: 'Needs human' }
}

function strippedKey(key: string): string {
  return key.startsWith('synthetic_') ? key.slice(10) : key
}

export function DocumentReview({ id, onClose }: { id: string; onClose: () => void }) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [direction, setDirection] = useState<DocumentDirection>('payable')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchDocumentDetail(id)
      .then((d) => {
        if (cancelled) return
        setDetail(d)
        setValues(d.extractedFields)
        setDirection(d.direction)
        if (d.hasOriginalFile) {
          fetchDocumentFileUrl(id)
            .then((url) => !cancelled && setFileUrl(url))
            .catch(() => {
              /* non-fatal — the review still works without the image */
            })
        }
      })
      .catch(() => !cancelled && setError('Could not load this document.'))
    return () => {
      cancelled = true
      if (fileUrl) URL.revokeObjectURL(fileUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const meta = useMemo(() => {
    if (!detail) return { confidence: {} as Record<string, number>, editable: {} as Record<string, boolean>, label: {} as Record<string, string> }
    const confidence: Record<string, number> = {}
    const editable: Record<string, boolean> = {}
    const label: Record<string, string> = {}
    for (const f of detail.extractionResult) {
      const key = strippedKey(f.key)
      confidence[key] = f.confidence
      editable[key] = f.editable
      label[key] = f.label
    }
    return { confidence, editable, label }
  }, [detail])

  const fieldKeys = detail ? Object.keys(detail.extractedFields) : []
  const needsReviewCount = fieldKeys.filter((k) => (meta.confidence[k] ?? 100) < 85).length
  const fieldsDirty = detail ? fieldKeys.some((k) => values[k] !== detail.extractedFields[k]) : false
  const directionDirty = detail ? direction !== detail.direction : false
  const dirty = fieldsDirty || directionDirty

  async function handleSave() {
    if (!detail) return
    const changed = Object.fromEntries(
      Object.entries(values).filter(([k, v]) => v !== detail.extractedFields[k])
    )
    if (Object.keys(changed).length === 0 && !directionDirty) return
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await updateDocumentFields(id, changed, directionDirty ? direction : undefined)
      setDetail(updated)
      setValues(updated.extractedFields)
      setDirection(updated.direction)
    } catch {
      setSaveError('Could not save your corrections. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  function handleReset() {
    if (detail) {
      setValues(detail.extractedFields)
      setDirection(detail.direction)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-30 flex items-center justify-center p-4 md:p-8"
      style={{ background: 'rgba(0,0,0,0.35)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 16, opacity: 0, scale: 0.98 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        exit={{ y: 16, opacity: 0, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-5xl rounded-2xl overflow-hidden flex flex-col"
        style={{ background: '#F5F2EC', border: '1px solid rgba(0,0,0,0.08)', maxHeight: '88vh' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b flex-shrink-0"
          style={{ borderColor: 'rgba(0,0,0,0.08)' }}
        >
          <div className="min-w-0">
            <h2 className="text-base font-semibold truncate" style={{ color: '#1A1816' }}>
              {detail ? detail.invoiceNo || detail.fileName || detail.fileId : 'Document Review'}
            </h2>
            {detail && (
              <p className="text-xs mt-0.5" style={{ color: '#A09890' }}>
                {DOC_TYPE_LABELS[detail.docType] ?? detail.docType} · {new Date(detail.createdAt).toLocaleString()}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {detail && ['GST_INVOICE', 'CREDIT_NOTE', 'DEBIT_NOTE'].includes(detail.docType) && (
              <div className="flex items-center gap-1 p-0.5 rounded-lg" style={{ background: 'rgba(0,0,0,0.05)' }}>
                <button
                  onClick={() => setDirection('payable')}
                  title="A bill this business received — money going out"
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium cursor-pointer transition-all"
                  style={{
                    background: direction === 'payable' ? '#FFFFFF' : 'transparent',
                    color: direction === 'payable' ? '#1A1816' : '#78726A',
                    boxShadow: direction === 'payable' ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
                  }}
                >
                  <ArrowDownToLine size={12} />
                  Payable
                </button>
                <button
                  onClick={() => setDirection('receivable')}
                  title="An invoice this business issued — money coming in"
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium cursor-pointer transition-all"
                  style={{
                    background: direction === 'receivable' ? '#FFFFFF' : 'transparent',
                    color: direction === 'receivable' ? '#1A1816' : '#78726A',
                    boxShadow: direction === 'receivable' ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
                  }}
                >
                  <ArrowUpFromLine size={12} />
                  Receivable
                </button>
              </div>
            )}
            {detail && <StatusBadge passed={detail.overallPassed} />}
            <button onClick={onClose} className="p-1 rounded-md cursor-pointer" style={{ color: '#78726A' }}>
              <X size={18} />
            </button>
          </div>
        </div>

        {error && <div className="px-5 py-8 text-sm text-center" style={{ color: '#DC2626' }}>{error}</div>}

        {!error && !detail && (
          <div className="flex items-center justify-center py-24">
            <Loader2 size={20} className="animate-spin" style={{ color: '#A09890' }} />
          </div>
        )}

        {detail && (
          <>
            <div className="flex-1 overflow-hidden grid grid-cols-1 md:grid-cols-[1fr_1.15fr]">
              {/* Left: original document */}
              <div
                className="overflow-y-auto flex items-start justify-center p-5 border-b md:border-b-0 md:border-r"
                style={{ borderColor: 'rgba(0,0,0,0.07)', background: 'rgba(0,0,0,0.02)' }}
              >
                {fileUrl ? (
                  <img src={fileUrl} alt="Original document" className="max-w-full rounded-lg shadow-sm" />
                ) : (
                  <div className="flex flex-col items-center gap-2 py-16 text-center">
                    <FileText size={24} style={{ color: '#A09890' }} />
                    <p className="text-xs" style={{ color: '#A09890' }}>
                      {detail.hasOriginalFile ? 'Loading original document…' : 'Original file was not retained.'}
                    </p>
                  </div>
                )}
              </div>

              {/* Right: fields, line items, validation */}
              <div className="overflow-y-auto p-5 space-y-6">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: '#A09890' }}>
                      Extracted Fields
                    </p>
                    <p className="text-[11px]" style={{ color: needsReviewCount > 0 ? '#B45309' : '#2E7D32' }}>
                      {fieldKeys.length} extracted
                      {needsReviewCount > 0 ? ` · ${needsReviewCount} need review` : ' · all high confidence'}
                    </p>
                  </div>
                  <div className="space-y-2">
                    {fieldKeys.length === 0 && (
                      <p className="text-xs" style={{ color: '#A09890' }}>No fields recorded.</p>
                    )}
                    {fieldKeys.map((key) => {
                      const conf = meta.confidence[key] ?? 100
                      const tier = confidenceTier(conf)
                      const isEditable = meta.editable[key] ?? true
                      return (
                        <div
                          key={key}
                          className="rounded-lg px-3 py-2"
                          style={{ background: tier.bg, border: `1px solid ${tier.color}22` }}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <label className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#78726A' }}>
                              {meta.label[key] ?? key.replace(/_/g, ' ')}
                            </label>
                            <span className="flex items-center gap-1.5">
                              <span
                                className="text-[9px] font-medium px-1.5 py-0.5 rounded-full"
                                style={{ color: tier.color, background: `${tier.color}1A` }}
                              >
                                {tier.label}
                              </span>
                              <span className="text-[10px] font-mono font-semibold" style={{ color: tier.color }}>
                                {Math.round(conf)}%
                              </span>
                            </span>
                          </div>
                          <input
                            value={values[key] ?? ''}
                            onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                            disabled={!isEditable}
                            className="w-full bg-transparent text-sm font-medium outline-none"
                            style={{
                              color: '#1A1816',
                              opacity: isEditable ? 1 : 0.6,
                              fontFamily: 'inherit',
                            }}
                          />
                        </div>
                      )
                    })}
                  </div>
                </div>

                {detail.lineItems.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: '#A09890' }}>
                      Line Items
                    </p>
                    <div className="rounded-lg overflow-hidden" style={{ border: '1px solid rgba(0,0,0,0.08)' }}>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr style={{ background: 'rgba(0,0,0,0.03)' }}>
                              {['Description', 'HSN/SAC', 'Qty', 'Rate', 'Amount'].map((h) => (
                                <th
                                  key={h}
                                  className="text-left px-3 py-2 font-semibold uppercase tracking-wider"
                                  style={{ color: '#A09890', fontSize: '10px' }}
                                >
                                  {h}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {detail.lineItems.map((li, i) => (
                              <tr key={i} style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                                <td className="px-3 py-2" style={{ color: '#1A1816' }}>{li.description || '—'}</td>
                                <td className="px-3 py-2" style={{ color: '#78726A' }}>{li.hsn_sac || '—'}</td>
                                <td className="px-3 py-2" style={{ color: '#78726A' }}>{li.quantity || '—'}</td>
                                <td className="px-3 py-2" style={{ color: '#78726A' }}>{li.rate || '—'}</td>
                                <td className="px-3 py-2 font-medium" style={{ color: '#1A1816' }}>{li.amount || '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: '#A09890' }}>
                    Validation Rules
                  </p>
                  <div className="space-y-1.5">
                    {detail.validationResult.rules.map((rule, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 px-3 py-2 rounded-lg text-xs"
                        style={{
                          background: rule.passed
                            ? 'rgba(46,125,50,0.06)'
                            : rule.severity === 'error'
                              ? 'rgba(220,38,38,0.06)'
                              : 'rgba(180,83,9,0.08)',
                        }}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0"
                          style={{
                            background: rule.passed ? '#2E7D32' : rule.severity === 'error' ? '#DC2626' : '#B45309',
                          }}
                        />
                        <div>
                          <p className="font-medium" style={{ color: '#1A1816' }}>{rule.name}</p>
                          <p style={{ color: '#78726A' }}>{rule.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {detail.corrections.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: '#A09890' }}>
                      Correction History
                    </p>
                    <div className="space-y-1.5">
                      {detail.corrections.map((c, i) => (
                        <div
                          key={i}
                          className="px-3 py-2 rounded-lg text-xs"
                          style={{ background: 'rgba(0,0,0,0.03)', border: '1px solid rgba(0,0,0,0.06)' }}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium" style={{ color: '#1A1816' }}>
                              {c.fieldName.replace(/_/g, ' ')}
                            </span>
                            <span style={{ color: '#A09890' }}>{new Date(c.createdAt).toLocaleString()}</span>
                          </div>
                          <p style={{ color: '#78726A' }}>
                            <span style={{ textDecoration: 'line-through' }}>{c.originalValue || '(empty)'}</span>
                            {' → '}
                            <span style={{ color: '#1A1816', fontWeight: 500 }}>{c.correctedValue}</span>
                            {c.modelConfidence != null && ` · model was ${Math.round(c.modelConfidence)}% confident`}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div
              className="flex items-center justify-between px-5 py-3.5 border-t flex-shrink-0"
              style={{ borderColor: 'rgba(0,0,0,0.08)' }}
            >
              {saveError ? (
                <p className="text-xs" style={{ color: '#DC2626' }}>{saveError}</p>
              ) : (
                <p className="text-xs" style={{ color: '#A09890' }}>
                  {dirty ? 'Unsaved changes' : 'No changes'}
                </p>
              )}
              <div className="flex items-center gap-2">
                {dirty && !saving && (
                  <button
                    onClick={handleReset}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium cursor-pointer"
                    style={{ color: '#78726A' }}
                  >
                    <RotateCcw size={13} /> Reset
                  </button>
                )}
                <button
                  onClick={handleSave}
                  disabled={!dirty || saving}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ background: '#4B6CB7' }}
                >
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                  Save & Re-validate
                </button>
              </div>
            </div>
          </>
        )}
      </motion.div>
    </motion.div>
  )
}
