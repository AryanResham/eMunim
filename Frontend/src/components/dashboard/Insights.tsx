import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  CalendarClock,
  Copy,
  FileWarning,
  Loader2,
  PieChart,
  Receipt,
  Repeat,
  ReceiptText,
  Tag,
  TrendingUp,
  Users,
  Pencil,
} from 'lucide-react'
import {
  fetchExpenseAnalytics,
  fetchCorrectionInsights,
  fetchFinanceInsights,
  fetchDocumentInsights,
  fetchReceivablesInsights,
  type ExpenseAnalytics,
  type CorrectionInsightRow,
  type FinanceInsights,
  type DocumentInsights,
  type ReceivablesInsights,
} from '@/api/backend'

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

function formatMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
}

function Panel({ title, icon: Icon, children }: { title: string; icon: typeof PieChart; children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl px-5 py-4"
      style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icon size={14} style={{ color: '#A09890' }} />
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: '#A09890' }}>
          {title}
        </p>
      </div>
      {children}
    </div>
  )
}

function EmptyRow({ text }: { text: string }) {
  return (
    <p className="text-sm" style={{ color: '#A09890' }}>
      {text}
    </p>
  )
}

export function Insights({ onOpenDocument }: { onOpenDocument?: (documentId: string) => void } = {}) {
  const [data, setData] = useState<ExpenseAnalytics | null>(null)
  const [finance, setFinance] = useState<FinanceInsights | null>(null)
  const [documents, setDocuments] = useState<DocumentInsights | null>(null)
  const [receivables, setReceivables] = useState<ReceivablesInsights | null>(null)
  const [corrections, setCorrections] = useState<CorrectionInsightRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetchExpenseAnalytics(),
      fetchCorrectionInsights(),
      fetchFinanceInsights(),
      fetchDocumentInsights(),
      fetchReceivablesInsights(),
    ])
      .then(([expenses, correctionRows, financeData, documentData, receivablesData]) => {
        if (cancelled) return
        setData(expenses)
        setCorrections(correctionRows)
        setFinance(financeData)
        setDocuments(documentData)
        setReceivables(receivablesData)
      })
      .catch(() => !cancelled && setError('Could not reach the backend. Make sure the API server is running.'))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={22} className="animate-spin" style={{ color: '#A09890' }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-8">
        <AlertTriangle size={22} style={{ color: '#DC2626' }} />
        <p className="text-sm font-medium" style={{ color: '#1A1816' }}>{error}</p>
      </div>
    )
  }

  const hasSpend = !!data && data.totalSpend > 0
  const hasRevenue = !!receivables && receivables.totalRevenue > 0

  if (!hasSpend && !hasRevenue) {
    return (
      <div
        className="rounded-xl px-6 py-10 text-center max-w-5xl mx-auto"
        style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
      >
        <PieChart size={24} style={{ color: '#A09890' }} className="mx-auto mb-2" />
        <p className="text-sm font-medium" style={{ color: '#1A1816' }}>No documents yet</p>
        <p className="text-xs mt-1" style={{ color: '#A09890' }}>
          Process a few documents to see spend and revenue insights here.
        </p>
      </div>
    )
  }

  // Promise.all only ever resolves these together, so by this point (past
  // loading/error) they're guaranteed non-null — this just narrows the type.
  if (!data || !finance || !documents || !receivables) return null

  const maxTrend = Math.max(1, ...data.monthlyTrend.map((r) => r.totalAmount))
  const topShare = data.vendorConcentration[0]?.share ?? 0
  const topCustomerShare = receivables.customerConcentration[0]?.share ?? 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="max-w-5xl mx-auto space-y-6"
    >
      {topCustomerShare >= 0.4 && (
        <div
          className="rounded-xl px-5 py-3 flex items-center gap-3"
          style={{ background: 'rgba(180,83,9,0.08)', border: '1px solid rgba(180,83,9,0.25)' }}
        >
          <AlertTriangle size={16} style={{ color: '#B45309' }} className="flex-shrink-0" />
          <p className="text-sm" style={{ color: '#1A1816' }}>
            <strong>{Math.round(topCustomerShare * 100)}%</strong> of your revenue depends on a single customer —{' '}
            <strong>{receivables.customerConcentration[0].name}</strong>.
          </p>
        </div>
      )}

      {topShare >= 0.4 && (
        <div
          className="rounded-xl px-5 py-3 flex items-center gap-3"
          style={{ background: 'rgba(180,83,9,0.08)', border: '1px solid rgba(180,83,9,0.25)' }}
        >
          <AlertTriangle size={16} style={{ color: '#B45309' }} className="flex-shrink-0" />
          <p className="text-sm" style={{ color: '#1A1816' }}>
            <strong>{Math.round(topShare * 100)}%</strong> of your spend depends on a single vendor —{' '}
            <strong>{data.vendorConcentration[0].name}</strong>.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="Vendor Concentration" icon={PieChart}>
          {data.vendorConcentration.length === 0 ? (
            <EmptyRow text="No vendor data yet." />
          ) : (
            <div className="space-y-2.5">
              {data.vendorConcentration.slice(0, 6).map((v) => (
                <div key={v.vendorKey} className="flex items-center gap-3">
                  <span className="text-sm w-32 flex-shrink-0 truncate" style={{ color: '#1A1816' }}>
                    {v.name}
                  </span>
                  <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.06)' }}>
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${v.share * 100}%`, background: '#4B6CB7' }}
                    />
                  </div>
                  <span className="text-xs w-10 text-right flex-shrink-0" style={{ color: '#A09890' }}>
                    {Math.round(v.share * 100)}%
                  </span>
                  <span className="text-xs w-20 text-right flex-shrink-0" style={{ color: '#78726A' }}>
                    {formatCurrency(v.totalAmount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Expense by Category" icon={Tag}>
          {data.byCategory.length === 0 ? (
            <EmptyRow text="No categorized spend yet." />
          ) : (
            <div className="space-y-2.5">
              {data.byCategory.slice(0, 6).map((c) => (
                <div key={c.category} className="flex items-center gap-3">
                  <span className="text-sm w-32 flex-shrink-0 truncate" style={{ color: '#1A1816' }}>
                    {c.category}
                  </span>
                  <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.06)' }}>
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${c.share * 100}%`, background: '#2E7D32' }}
                    />
                  </div>
                  <span className="text-xs w-10 text-right flex-shrink-0" style={{ color: '#A09890' }}>
                    {Math.round(c.share * 100)}%
                  </span>
                  <span className="text-xs w-20 text-right flex-shrink-0" style={{ color: '#78726A' }}>
                    {formatCurrency(c.totalAmount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Monthly Spend Trend" icon={TrendingUp}>
          {data.monthlyTrend.length === 0 ? (
            <EmptyRow text="No trend data yet." />
          ) : (
            <div className="flex items-end gap-2 h-32">
              {data.monthlyTrend.slice(-6).map((r) => (
                <div key={r.month} className="flex-1 flex flex-col items-center gap-1.5">
                  <div className="w-full flex-1 flex items-end">
                    <div
                      className="w-full rounded-t-md"
                      style={{
                        height: `${Math.max(4, (r.totalAmount / maxTrend) * 100)}%`,
                        background: '#4B6CB7',
                      }}
                      title={formatCurrency(r.totalAmount)}
                    />
                  </div>
                  <span className="text-[10px]" style={{ color: '#A09890' }}>
                    {formatMonth(r.month)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Recurring Vendors" icon={Repeat}>
          {data.recurringVendors.length === 0 ? (
            <EmptyRow text="Not enough history to detect recurring vendors yet." />
          ) : (
            <div className="space-y-2">
              {data.recurringVendors.slice(0, 6).map((v) => (
                <div key={v.vendorKey} className="flex items-center justify-between text-sm">
                  <span className="truncate max-w-[160px]" style={{ color: '#1A1816' }}>
                    {v.name}
                  </span>
                  <span style={{ color: '#78726A' }}>
                    {formatCurrency(v.avgMonthlyAmount)}/mo · ~{formatCurrency(v.estimatedAnnualAmount)}/yr
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Spend Anomalies" icon={AlertTriangle}>
          {data.monthlyAnomalies.length === 0 ? (
            <EmptyRow text="No unusual monthly spend spikes detected." />
          ) : (
            <div className="space-y-2">
              {data.monthlyAnomalies.slice(0, 6).map((a) => (
                <div key={`${a.vendorKey}-${a.month}`} className="flex items-center justify-between text-sm">
                  <span className="truncate max-w-[140px]" style={{ color: '#1A1816' }}>
                    {a.name}
                  </span>
                  <span style={{ color: '#B45309' }}>
                    +{a.pctIncrease.toFixed(0)}% ({formatCurrency(a.currentAmount)} vs avg{' '}
                    {formatCurrency(a.priorAvgAmount)})
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Most-Corrected Fields" icon={Pencil}>
          {corrections.length === 0 ? (
            <EmptyRow text="No corrections logged yet." />
          ) : (
            <div className="space-y-2">
              {corrections.slice(0, 6).map((c) => (
                <div key={c.fieldName} className="flex items-center justify-between text-sm">
                  <span className="truncate max-w-[160px]" style={{ color: '#1A1816' }}>
                    {c.fieldName.replace(/_/g, ' ')}
                  </span>
                  <span style={{ color: '#78726A' }}>
                    {c.correctionCount} correction{c.correctionCount !== 1 ? 's' : ''}
                    {c.avgModelConfidence != null && ` · ${Math.round(c.avgModelConfidence)}% avg confidence`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="GST Input Tax Credit" icon={Receipt}>
          {!finance || finance.itc.totalItc === 0 ? (
            <EmptyRow text="No GST amounts extracted yet." />
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ['CGST', finance.itc.totalCgst],
                  ['SGST', finance.itc.totalSgst],
                  ['IGST', finance.itc.totalIgst],
                ].map(([label, amount]) => (
                  <div key={label as string}>
                    <p className="text-[10px] uppercase tracking-wider" style={{ color: '#A09890' }}>
                      {label}
                    </p>
                    <p className="text-sm font-medium" style={{ color: '#1A1816' }}>
                      {formatCurrency(amount as number)}
                    </p>
                  </div>
                ))}
              </div>
              <div className="pt-2 flex items-center justify-between text-sm" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                <span style={{ color: '#78726A' }}>Potential ITC</span>
                <span className="font-semibold" style={{ color: '#2E7D32' }}>
                  {formatCurrency(finance.itc.totalItc)}
                </span>
              </div>
              {finance.itc.exceptions.length > 0 && (
                <div className="pt-1 space-y-1">
                  {finance.itc.exceptions.slice(0, 4).map((e) => (
                    <div key={e.documentId} className="flex items-center justify-between text-xs">
                      <span className="truncate max-w-[140px]" style={{ color: '#1A1816' }}>
                        {e.vendorName}
                      </span>
                      <span style={{ color: '#DC2626' }}>{e.reason}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Panel>

        <Panel title="Payables Due" icon={CalendarClock}>
          {!finance || finance.payables.items.length === 0 ? (
            <EmptyRow text="No documents with a due date extracted yet." />
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ['Overdue', finance.payables.overdueTotal, '#DC2626'],
                  ['Due ≤7d', finance.payables.dueSoonTotal, '#B45309'],
                  ['Upcoming', finance.payables.upcomingTotal, '#78726A'],
                ].map(([label, amount, color]) => (
                  <div key={label as string}>
                    <p className="text-[10px] uppercase tracking-wider" style={{ color: '#A09890' }}>
                      {label}
                    </p>
                    <p className="text-sm font-medium" style={{ color: color as string }}>
                      {formatCurrency(amount as number)}
                    </p>
                  </div>
                ))}
              </div>
              <div className="pt-2 space-y-1.5" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                {finance.payables.items.slice(0, 5).map((p) => (
                  <div key={p.documentId} className="flex items-center justify-between text-sm">
                    <span className="truncate max-w-[130px]" style={{ color: '#1A1816' }}>
                      {p.vendorName}
                    </span>
                    <span style={{ color: p.bucket === 'overdue' ? '#DC2626' : p.bucket === 'due_soon' ? '#B45309' : '#78726A' }}>
                      {formatCurrency(p.amount)} · {p.daysUntilDue < 0 ? `${Math.abs(p.daysUntilDue)}d overdue` : `in ${p.daysUntilDue}d`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Vendor Price Increases" icon={TrendingUp}>
          {!finance || finance.priceAlerts.length === 0 ? (
            <EmptyRow text="No line-item price increases detected." />
          ) : (
            <div className="space-y-2">
              {finance.priceAlerts.slice(0, 6).map((p) => (
                <div key={`${p.vendorKey}-${p.description}`} className="flex items-center justify-between text-sm">
                  <span className="truncate max-w-[160px]" style={{ color: '#1A1816' }}>
                    {p.vendorName} — {p.description}
                  </span>
                  <span style={{ color: '#B45309' }}>
                    +{p.pctIncrease.toFixed(0)}% ({formatCurrency(p.previousRate)} → {formatCurrency(p.currentRate)})
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Credit/Debit Note Netting" icon={ReceiptText}>
          {!documents || documents.creditDebitNetting.length === 0 ? (
            <EmptyRow text="No credit or debit notes to net against invoices yet." />
          ) : (
            <div className="space-y-2">
              {documents.creditDebitNetting.slice(0, 6).map((n) => (
                <div key={n.vendorKey} className="flex items-center justify-between text-sm">
                  <span className="truncate max-w-[140px]" style={{ color: '#1A1816' }}>
                    {n.name}
                    {n.highCreditNoteRate && (
                      <span className="ml-1.5 text-xs" style={{ color: '#B45309' }}>
                        ({Math.round((n.creditNoteRate ?? 0) * 100)}% credit rate)
                      </span>
                    )}
                  </span>
                  <span style={{ color: '#78726A' }}>
                    Net {formatCurrency(n.netPayable)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Lapsed Vendors" icon={Repeat}>
          {!documents || documents.lapsedVendors.length === 0 ? (
            <EmptyRow text="No previously-regular vendors have gone quiet." />
          ) : (
            <div className="space-y-2">
              {documents.lapsedVendors.slice(0, 6).map((v) => (
                <div key={v.vendorKey} className="flex items-center justify-between text-sm">
                  <span className="truncate max-w-[150px]" style={{ color: '#1A1816' }}>
                    {v.name}
                  </span>
                  <span style={{ color: '#78726A' }}>
                    quiet {v.monthsSinceLastInvoice}mo · was {formatCurrency(v.avgMonthlyAmount)}/mo
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Possible Duplicates" icon={Copy}>
          {!documents || documents.duplicateClusters.length === 0 ? (
            <EmptyRow text="No likely duplicate documents found." />
          ) : (
            <div className="space-y-2">
              {documents.duplicateClusters.slice(0, 6).map((c) => (
                <button
                  key={`${c.documentId}-${c.otherDocumentId}`}
                  onClick={() => onOpenDocument?.(c.documentId)}
                  className="w-full flex items-center justify-between text-sm text-left cursor-pointer"
                >
                  <span className="truncate max-w-[150px]" style={{ color: '#1A1816' }}>
                    {c.vendorName}
                  </span>
                  <span style={{ color: c.score >= 90 ? '#DC2626' : '#B45309' }}>
                    {c.score}% match — {c.reasons.join(', ')}
                  </span>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Needs a Second Look" icon={FileWarning}>
          {!documents || documents.lowConfidenceQueue.length === 0 ? (
            <EmptyRow text="No documents with low extraction confidence." />
          ) : (
            <div className="space-y-2">
              {documents.lowConfidenceQueue.slice(0, 6).map((q) => (
                <button
                  key={q.documentId}
                  onClick={() => onOpenDocument?.(q.documentId)}
                  className="w-full flex items-center justify-between text-sm text-left cursor-pointer"
                >
                  <span className="truncate max-w-[150px]" style={{ color: '#1A1816' }}>
                    {q.vendorName}
                  </span>
                  <span style={{ color: '#78726A' }}>
                    {Math.round(q.avgConfidence)}% avg confidence · {q.lowConfidenceFieldCount} field(s)
                  </span>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Customer Concentration" icon={Users}>
          {receivables.customerConcentration.length === 0 ? (
            <EmptyRow text="No receivable revenue yet — invoices you've issued will show up here." />
          ) : (
            <div className="space-y-2.5">
              {receivables.customerConcentration.slice(0, 6).map((c) => (
                <div key={c.vendorKey} className="flex items-center gap-3">
                  <span className="text-sm w-32 flex-shrink-0 truncate" style={{ color: '#1A1816' }}>
                    {c.name}
                  </span>
                  <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.06)' }}>
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${c.share * 100}%`, background: '#0E7490' }}
                    />
                  </div>
                  <span className="text-xs w-10 text-right flex-shrink-0" style={{ color: '#A09890' }}>
                    {Math.round(c.share * 100)}%
                  </span>
                  <span className="text-xs w-20 text-right flex-shrink-0" style={{ color: '#78726A' }}>
                    {formatCurrency(c.totalAmount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Receivables Due" icon={CalendarClock}>
          {receivables.receivablesAging.items.length === 0 ? (
            <EmptyRow text="No receivable documents with a due date extracted yet." />
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ['Overdue', receivables.receivablesAging.overdueTotal, '#DC2626'],
                  ['Due ≤7d', receivables.receivablesAging.dueSoonTotal, '#B45309'],
                  ['Upcoming', receivables.receivablesAging.upcomingTotal, '#78726A'],
                ].map(([label, amount, color]) => (
                  <div key={label as string}>
                    <p className="text-[10px] uppercase tracking-wider" style={{ color: '#A09890' }}>
                      {label}
                    </p>
                    <p className="text-sm font-medium" style={{ color: color as string }}>
                      {formatCurrency(amount as number)}
                    </p>
                  </div>
                ))}
              </div>
              <div className="pt-2 space-y-1.5" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                {receivables.receivablesAging.items.slice(0, 5).map((r) => (
                  <div key={r.documentId} className="flex items-center justify-between text-sm">
                    <span className="truncate max-w-[130px]" style={{ color: '#1A1816' }}>
                      {r.vendorName}
                    </span>
                    <span style={{ color: r.bucket === 'overdue' ? '#DC2626' : r.bucket === 'due_soon' ? '#B45309' : '#78726A' }}>
                      {formatCurrency(r.amount)} · {r.daysUntilDue < 0 ? `${Math.abs(r.daysUntilDue)}d overdue` : `in ${r.daysUntilDue}d`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      </div>
    </motion.div>
  )
}
