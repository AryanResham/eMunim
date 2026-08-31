import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { FileText, IndianRupee, TrendingUp, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'
import {
  fetchDocumentsSummary,
  fetchDocuments,
  fetchExpenseAnalytics,
  fetchReceivablesInsights,
  type DocumentSummaryRow,
  type DocumentRecord,
} from '@/api/backend'
import type { DocType } from '@/types/upload'

function DirectionBadge({ direction }: { direction: DocumentRecord['direction'] }) {
  const payable = direction === 'payable'
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
      style={{
        background: payable ? 'rgba(75,108,183,0.1)' : 'rgba(14,116,144,0.1)',
        color: payable ? '#4B6CB7' : '#0E7490',
      }}
    >
      {payable ? 'Payable' : 'Receivable'}
    </span>
  )
}

const DOC_TYPE_LABELS: Record<DocType, string> = {
  GST_INVOICE: 'GST Tax Invoice',
  PURCHASE_BILL: 'Purchase Bill',
  EXPENSE_RECEIPT: 'Expense Receipt',
  UTILITY_BILL: 'Utility Bill',
  CREDIT_NOTE: 'Credit Note',
  DEBIT_NOTE: 'Debit Note',
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: typeof FileText
  label: string
  value: string
  accent: string
}) {
  return (
    <div
      className="rounded-xl px-5 py-4 flex items-center gap-4"
      style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
    >
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: `${accent}1A` }}
      >
        <Icon size={18} style={{ color: accent }} />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: '#A09890' }}>
          {label}
        </p>
        <p className="text-xl font-semibold truncate" style={{ color: '#1A1816' }}>
          {value}
        </p>
      </div>
    </div>
  )
}

export function Dashboard() {
  const [summary, setSummary] = useState<DocumentSummaryRow[] | null>(null)
  const [recent, setRecent] = useState<DocumentRecord[] | null>(null)
  const [totalSpend, setTotalSpend] = useState(0)
  const [totalRevenue, setTotalRevenue] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [summaryData, recentData, expenseData, receivablesData] = await Promise.all([
          fetchDocumentsSummary(),
          fetchDocuments({ page: 1, pageSize: 8 }),
          fetchExpenseAnalytics(),
          fetchReceivablesInsights(),
        ])
        if (cancelled) return
        setSummary(summaryData)
        setRecent(recentData.documents)
        setTotalSpend(expenseData.totalSpend)
        setTotalRevenue(receivablesData.totalRevenue)
      } catch (err) {
        if (cancelled) return
        console.error('Dashboard load failed:', err)
        setError('Could not reach the backend. Make sure the API server is running.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
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

  const totalCount = summary?.reduce((sum, row) => sum + row.count, 0) ?? 0
  const passedCount = recent?.filter((d) => d.overallPassed).length ?? 0
  const failedCount = recent?.filter((d) => !d.overallPassed).length ?? 0
  const maxCount = Math.max(1, ...(summary ?? []).map((r) => r.count))

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="max-w-5xl mx-auto space-y-6"
    >
      {totalCount === 0 ? (
        <div
          className="rounded-xl px-6 py-10 text-center"
          style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
        >
          <FileText size={24} style={{ color: '#A09890' }} className="mx-auto mb-2" />
          <p className="text-sm font-medium" style={{ color: '#1A1816' }}>No documents processed yet</p>
          <p className="text-xs mt-1" style={{ color: '#A09890' }}>
            Upload and validate a document to see it show up here.
          </p>
        </div>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <StatCard icon={FileText} label="Total Documents" value={String(totalCount)} accent="#4B6CB7" />
            <StatCard icon={IndianRupee} label="Total Spend" value={formatCurrency(totalSpend)} accent="#4B6CB7" />
            <StatCard icon={TrendingUp} label="Total Revenue" value={formatCurrency(totalRevenue)} accent="#0E7490" />
            <StatCard
              icon={failedCount > 0 ? AlertTriangle : CheckCircle2}
              label="Recent Pass Rate"
              value={recent && recent.length > 0 ? `${passedCount}/${recent.length} passed` : '—'}
              accent={failedCount > 0 ? '#B45309' : '#2E7D32'}
            />
          </div>

          {/* Breakdown by doc type */}
          <div
            className="rounded-xl px-5 py-4"
            style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
          >
            <p className="text-[11px] font-semibold uppercase tracking-wider mb-3" style={{ color: '#A09890' }}>
              By Document Type
            </p>
            <div className="space-y-2.5">
              {summary!.map((row) => (
                <div key={row.docType} className="flex items-center gap-3">
                  <span className="text-sm w-40 flex-shrink-0 truncate" style={{ color: '#1A1816' }}>
                    {DOC_TYPE_LABELS[row.docType] ?? row.docType}
                  </span>
                  <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.06)' }}>
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${(row.count / maxCount) * 100}%`, background: '#4B6CB7' }}
                    />
                  </div>
                  <span className="text-xs w-8 text-right flex-shrink-0" style={{ color: '#A09890' }}>
                    {row.count}
                  </span>
                  <span className="text-xs w-24 text-right flex-shrink-0" style={{ color: '#78726A' }}>
                    {formatCurrency(row.totalAmount)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent documents */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
          >
            <p
              className="text-[11px] font-semibold uppercase tracking-wider px-5 pt-4 pb-3"
              style={{ color: '#A09890' }}
            >
              Recent Documents
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                    {['Document', 'Type', 'Counterparty', 'Direction', 'Amount', 'Status', 'Date'].map((h) => (
                      <th
                        key={h}
                        className="text-left px-5 py-2 text-[11px] font-semibold uppercase tracking-wider"
                        style={{ color: '#A09890' }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recent!.map((doc) => (
                    <tr key={doc.id} style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                      <td className="px-5 py-2.5 truncate max-w-[180px]" style={{ color: '#1A1816' }}>
                        {doc.invoiceNo || doc.fileName || doc.fileId}
                      </td>
                      <td className="px-5 py-2.5" style={{ color: '#78726A' }}>
                        {DOC_TYPE_LABELS[doc.docType] ?? doc.docType}
                      </td>
                      <td className="px-5 py-2.5 truncate max-w-[160px]" style={{ color: '#78726A' }}>
                        {(doc.direction === 'receivable' ? doc.buyerName : doc.vendorName) || '—'}
                      </td>
                      <td className="px-5 py-2.5">
                        <DirectionBadge direction={doc.direction} />
                      </td>
                      <td className="px-5 py-2.5" style={{ color: '#1A1816' }}>
                        {doc.totalAmount != null ? formatCurrency(doc.totalAmount) : '—'}
                      </td>
                      <td className="px-5 py-2.5">
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                          style={{
                            background: doc.overallPassed ? 'rgba(46,125,50,0.1)' : 'rgba(220,38,38,0.1)',
                            color: doc.overallPassed ? '#2E7D32' : '#DC2626',
                          }}
                        >
                          {doc.overallPassed ? 'Passed' : 'Needs Review'}
                        </span>
                      </td>
                      <td className="px-5 py-2.5" style={{ color: '#A09890' }}>
                        {new Date(doc.createdAt).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </motion.div>
  )
}
