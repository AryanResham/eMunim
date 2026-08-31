import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronLeft as BackIcon,
  Loader2,
  AlertTriangle,
  FileText,
  Folder,
  Users,
  List,
} from 'lucide-react'
import {
  fetchDocuments,
  fetchVendorProfiles,
  fetchCustomerProfiles,
  type DocumentRecord,
  type DocumentDirection,
  type VendorProfile,
} from '@/api/backend'
import { DocumentReview } from './DocumentReview'
import type { DocType } from '@/types/upload'

const DOC_TYPE_LABELS: Record<DocType, string> = {
  GST_INVOICE: 'GST Tax Invoice',
  PURCHASE_BILL: 'Purchase Bill',
  EXPENSE_RECEIPT: 'Expense Receipt',
  UTILITY_BILL: 'Utility Bill',
  CREDIT_NOTE: 'Credit Note',
  DEBIT_NOTE: 'Debit Note',
}

const DOC_TYPES = Object.keys(DOC_TYPE_LABELS) as DocType[]
const PAGE_SIZE = 15

const FOLDER_PALETTE = ['#4B6CB7', '#2E7D32', '#B45309', '#7C3AED', '#0E7490', '#BE185D']

function folderColor(key: string): string {
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  return FOLDER_PALETTE[hash % FOLDER_PALETTE.length]
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

function StatusBadge({ passed }: { passed: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
      style={{
        background: passed ? 'rgba(46,125,50,0.1)' : 'rgba(220,38,38,0.1)',
        color: passed ? '#2E7D32' : '#DC2626',
      }}
    >
      {passed ? 'Passed' : 'Needs Review'}
    </span>
  )
}

// Same 85 / 60 boundaries as DocumentReview's per-field tiers, applied to a document's
// average extraction confidence — the auto-accept / review / human-required split.
function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence == null) return <span style={{ color: '#A09890' }}>—</span>
  const tier =
    confidence >= 85
      ? { color: '#2E7D32', bg: 'rgba(46,125,50,0.1)', label: 'Auto-accepted' }
      : confidence >= 60
        ? { color: '#B45309', bg: 'rgba(180,83,9,0.1)', label: 'Review recommended' }
        : { color: '#DC2626', bg: 'rgba(220,38,38,0.1)', label: 'Needs human' }
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ background: tier.bg, color: tier.color }}
      title={`${Math.round(confidence)}% average extraction confidence`}
    >
      {tier.label}
    </span>
  )
}

function DirectionBadge({ direction }: { direction: DocumentDirection }) {
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

function CounterpartyFolder({
  profile,
  direction,
  onOpen,
}: {
  profile: VendorProfile
  direction: DocumentDirection
  onOpen: () => void
}) {
  const color = folderColor(profile.vendorKey)
  return (
    <motion.button
      onClick={onOpen}
      whileHover={{ y: -3 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.15 }}
      className="relative text-left rounded-xl px-4 pt-4 pb-3.5 cursor-pointer overflow-hidden"
      style={{ background: 'rgba(255,255,255,0.65)', border: '1px solid rgba(0,0,0,0.08)' }}
    >
      {/* Folder tab */}
      <div
        className="absolute -top-0 left-4 w-10 h-2 rounded-b-md"
        style={{ background: color, opacity: 0.85 }}
      />
      <div className="flex items-start justify-between mb-3">
        <div
          className="w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${color}1F` }}
        >
          <Folder size={20} style={{ color }} fill={`${color}33`} />
        </div>
        {profile.flaggedCount > 0 && (
          <span
            className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold"
            style={{ background: 'rgba(220,38,38,0.1)', color: '#DC2626' }}
          >
            {profile.flaggedCount} flagged
          </span>
        )}
      </div>
      <p className="text-sm font-semibold truncate" style={{ color: '#1A1816' }}>
        {profile.name}
      </p>
      <p className="text-xs mt-0.5" style={{ color: '#A09890' }}>
        {profile.documentCount} document{profile.documentCount !== 1 ? 's' : ''}
      </p>
      <div className="flex items-center justify-between mt-2.5 pt-2.5" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        <span className="text-xs" style={{ color: '#78726A' }}>
          {direction === 'payable' ? 'Total paid' : 'Total invoiced'}
        </span>
        <span className="text-sm font-semibold" style={{ color: '#1A1816' }}>
          {formatCurrency(profile.totalAmount)}
        </span>
      </div>
    </motion.button>
  )
}

interface RecordsSearchSeed {
  query: string
  nonce: number
}

interface RecordsOpenSeed {
  documentId: string
  nonce: number
}

interface SelectedCounterparty {
  profile: VendorProfile
  direction: DocumentDirection
}

type ViewMode = 'payees' | 'customers' | 'all'

export function Records({
  searchSeed,
  openSeed,
}: { searchSeed?: RecordsSearchSeed | null; openSeed?: RecordsOpenSeed | null } = {}) {
  const [viewMode, setViewMode] = useState<ViewMode>('payees')
  const [vendors, setVendors] = useState<VendorProfile[] | null>(null)
  const [customers, setCustomers] = useState<VendorProfile[] | null>(null)
  const [countersLoading, setCountersLoading] = useState(true)
  const [countersError, setCountersError] = useState<string | null>(null)
  const [selectedCounterparty, setSelectedCounterparty] = useState<SelectedCounterparty | null>(null)

  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [docType, setDocType] = useState<DocType | ''>('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  // Bumped whenever a document might have changed underneath us (e.g. its
  // direction was flipped in the Review workspace) — forces the folder lists
  // and any open folder's document list to refetch instead of going stale.
  const [refreshNonce, setRefreshNonce] = useState(0)

  const showDocumentList = viewMode === 'all' || selectedCounterparty !== null

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchVendorProfiles(), fetchCustomerProfiles()])
      .then(([v, c]) => {
        if (cancelled) return
        setVendors(v)
        setCustomers(c)
      })
      .catch(() => !cancelled && setCountersError('Could not load payees and customers.'))
      .finally(() => !cancelled && setCountersLoading(false))
    return () => {
      cancelled = true
    }
  }, [refreshNonce])

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 350)
    return () => clearTimeout(t)
  }, [searchInput])

  // Jump straight to a search when it arrives from the header search box
  useEffect(() => {
    if (!searchSeed) return
    setViewMode('all')
    setSelectedCounterparty(null)
    setSearchInput(searchSeed.query)
    setSearch(searchSeed.query)
  }, [searchSeed?.nonce])

  // Open a specific document's review panel directly, e.g. from a notification
  useEffect(() => {
    if (!openSeed) return
    setSelectedId(openSeed.documentId)
  }, [openSeed?.nonce])

  useEffect(() => {
    if (!showDocumentList) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchDocuments({
      page,
      pageSize: PAGE_SIZE,
      docType: docType || undefined,
      search: search || undefined,
      vendorKey: selectedCounterparty?.profile.vendorKey,
      direction: selectedCounterparty?.direction,
    })
      .then((result) => {
        if (cancelled) return
        setDocuments(result.documents)
        setTotal(result.total)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Records load failed:', err)
        setError('Could not reach the backend. Make sure the API server is running.')
      })
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [showDocumentList, page, docType, search, selectedCounterparty, refreshNonce])

  useEffect(() => {
    setPage(1)
  }, [docType, search, selectedCounterparty])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function openCounterparty(profile: VendorProfile, direction: DocumentDirection) {
    setSelectedCounterparty({ profile, direction })
    setDocType('')
    setSearchInput('')
    setSearch('')
  }

  function backToFolders() {
    setSelectedCounterparty(null)
    setDocType('')
    setSearchInput('')
    setSearch('')
  }

  const folderLabel = viewMode === 'customers' ? 'Customers' : 'Payees'
  const folderList = viewMode === 'customers' ? customers : vendors

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* View toggle + breadcrumb */}
      <div className="flex items-center justify-between gap-2.5">
        {selectedCounterparty ? (
          <button
            onClick={backToFolders}
            className="flex items-center gap-1.5 text-sm font-medium cursor-pointer"
            style={{ color: '#4B6CB7' }}
          >
            <BackIcon size={15} />
            {selectedCounterparty.direction === 'receivable' ? 'Customers' : 'Payees'}
            <span style={{ color: '#A09890' }}>/</span>
            <span style={{ color: '#1A1816' }}>{selectedCounterparty.profile.name}</span>
          </button>
        ) : (
          <div className="flex items-center gap-1 p-0.5 rounded-lg" style={{ background: 'rgba(0,0,0,0.05)' }}>
            {(
              [
                { mode: 'payees' as const, label: 'Payees', icon: Folder },
                { mode: 'customers' as const, label: 'Customers', icon: Users },
                { mode: 'all' as const, label: 'All Documents', icon: List },
              ]
            ).map(({ mode, label, icon: Icon }) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium cursor-pointer transition-all"
                style={{
                  background: viewMode === mode ? '#FFFFFF' : 'transparent',
                  color: viewMode === mode ? '#1A1816' : '#78726A',
                  boxShadow: viewMode === mode ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
                }}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Counterparty folder grid */}
      {(viewMode === 'payees' || viewMode === 'customers') && !selectedCounterparty && (
        <>
          {countersLoading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={20} className="animate-spin" style={{ color: '#A09890' }} />
            </div>
          )}
          {!countersLoading && countersError && (
            <div className="flex flex-col items-center justify-center gap-2 py-20 text-center">
              <AlertTriangle size={20} style={{ color: '#DC2626' }} />
              <p className="text-sm font-medium" style={{ color: '#1A1816' }}>{countersError}</p>
            </div>
          )}
          {!countersLoading && !countersError && folderList && folderList.length === 0 && (
            <div
              className="rounded-xl px-6 py-14 text-center"
              style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
            >
              <Folder size={22} style={{ color: '#A09890' }} className="mx-auto mb-2" />
              <p className="text-sm font-medium" style={{ color: '#1A1816' }}>No {folderLabel.toLowerCase()} yet</p>
              <p className="text-xs mt-1" style={{ color: '#A09890' }}>
                {viewMode === 'customers'
                  ? 'Invoices you issue to customers will show up here.'
                  : 'Process a document to see who it was paid to.'}
              </p>
            </div>
          )}
          {!countersLoading && !countersError && folderList && folderList.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {folderList.map((p) => (
                <CounterpartyFolder
                  key={p.vendorKey}
                  profile={p}
                  direction={viewMode === 'customers' ? 'receivable' : 'payable'}
                  onOpen={() => openCounterparty(p, viewMode === 'customers' ? 'receivable' : 'payable')}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Filters — shown in All Documents mode and inside an opened folder */}
      {showDocumentList && (
        <div className="flex flex-wrap items-center gap-2.5">
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm flex-1 min-w-[200px]"
            style={{ background: 'rgba(0,0,0,0.05)', border: '1px solid rgba(0,0,0,0.09)' }}
          >
            <Search size={14} style={{ color: '#A09890' }} />
            <input
              type="text"
              placeholder="Search invoice no., counterparty, file name..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="bg-transparent border-none outline-none text-sm w-full"
              style={{ color: '#1A1816' }}
            />
          </div>

          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value as DocType | '')}
            className="px-3 py-2 rounded-lg text-sm cursor-pointer"
            style={{ background: 'rgba(0,0,0,0.05)', border: '1px solid rgba(0,0,0,0.09)', color: '#1A1816' }}
          >
            <option value="">All Types</option>
            {DOC_TYPES.map((dt) => (
              <option key={dt} value={dt}>{DOC_TYPE_LABELS[dt]}</option>
            ))}
          </select>
        </div>
      )}

      {/* Table */}
      {showDocumentList && loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={20} className="animate-spin" style={{ color: '#A09890' }} />
        </div>
      )}

      {showDocumentList && !loading && error && (
        <div className="flex flex-col items-center justify-center gap-2 py-20 text-center">
          <AlertTriangle size={20} style={{ color: '#DC2626' }} />
          <p className="text-sm font-medium" style={{ color: '#1A1816' }}>{error}</p>
        </div>
      )}

      {showDocumentList && !loading && !error && documents && documents.length === 0 && (
        <div
          className="rounded-xl px-6 py-14 text-center"
          style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
        >
          <FileText size={22} style={{ color: '#A09890' }} className="mx-auto mb-2" />
          <p className="text-sm font-medium" style={{ color: '#1A1816' }}>No matching records</p>
          <p className="text-xs mt-1" style={{ color: '#A09890' }}>
            {search || docType ? 'Try adjusting your filters.' : 'Process a document to see it show up here.'}
          </p>
        </div>
      )}

      {showDocumentList && !loading && !error && documents && documents.length > 0 && (
        <>
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    {(viewMode === 'all'
                      ? ['Document', 'Type', 'Counterparty', 'Direction', 'Amount', 'Status', 'Confidence', 'Date']
                      : ['Document', 'Type', 'Amount', 'Status', 'Confidence', 'Date']
                    ).map((h) => (
                      <th
                        key={h}
                        className="text-left px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider"
                        style={{ color: '#A09890' }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr
                      key={doc.id}
                      onClick={() => setSelectedId(doc.id)}
                      className="cursor-pointer"
                      style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'rgba(0,0,0,0.03)' }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'transparent' }}
                    >
                      <td className="px-5 py-2.5 truncate max-w-[180px]" style={{ color: '#1A1816' }}>
                        {doc.invoiceNo || doc.fileName || doc.fileId}
                      </td>
                      <td className="px-5 py-2.5" style={{ color: '#78726A' }}>
                        {DOC_TYPE_LABELS[doc.docType] ?? doc.docType}
                      </td>
                      {viewMode === 'all' && (
                        <>
                          <td className="px-5 py-2.5 truncate max-w-[160px]" style={{ color: '#78726A' }}>
                            {(doc.direction === 'receivable' ? doc.buyerName : doc.vendorName) || '—'}
                          </td>
                          <td className="px-5 py-2.5">
                            <DirectionBadge direction={doc.direction} />
                          </td>
                        </>
                      )}
                      <td className="px-5 py-2.5" style={{ color: '#1A1816' }}>
                        {doc.totalAmount != null ? formatCurrency(doc.totalAmount) : '—'}
                      </td>
                      <td className="px-5 py-2.5">
                        <StatusBadge passed={doc.overallPassed} />
                      </td>
                      <td className="px-5 py-2.5">
                        <ConfidenceBadge confidence={doc.avgConfidence} />
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

          {/* Pagination */}
          <div className="flex items-center justify-between px-1">
            <p className="text-xs" style={{ color: '#A09890' }}>
              {total} record{total !== 1 ? 's' : ''} · page {page} of {totalPages}
            </p>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ border: '1px solid rgba(0,0,0,0.09)', color: '#78726A' }}
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ border: '1px solid rgba(0,0,0,0.09)', color: '#78726A' }}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </>
      )}

      <AnimatePresence>
        {selectedId && (
          <DocumentReview
            id={selectedId}
            onClose={() => {
              setSelectedId(null)
              setRefreshNonce((n) => n + 1)
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
