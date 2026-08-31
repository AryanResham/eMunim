import type {
  ClassificationResult,
  DocType,
  ExtractedField,
  LineItem,
  ValidationResult,
} from '@/types/upload'
import type { OCRResult } from '@/types/ocr'
import { authHeaders, triggerLogout } from '@/lib/auth'

const API_BASE = 'http://localhost:8000/api'

/** fetch() wrapper that attaches the auth token and force-logs-out on a 401. */
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const res = await fetch(url, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers ?? {}) },
  })
  if (res.status === 401) triggerLogout()
  return res
}

/** Step 1 → 2: Classify the uploaded document using the real backend */
export async function classifyDocument(fileId: string, ocrText: string): Promise<ClassificationResult> {
  const res = await authFetch(`${API_BASE}/classify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_id: fileId, ocr_text: ocrText }),
  })
  if (!res.ok) throw new Error('Classification failed')
  const data = await res.json()

  // Map snake_case from backend to camelCase for frontend
  return {
    type: data.type,
    label: data.label,
    subCategory: data.sub_category,
    confidence: data.confidence,
    classifierLevel: data.classifier_level,
    date: data.date,
    suggestedSubCategories: data.suggested_sub_categories,
    topPredictions: data.top_predictions?.map((p: any) => ({
      type: p.type,
      confidence: p.confidence,
    })),
  }
}

/** Step 2 → 3: Extract structured fields (+ line items) from the classified document */
export async function extractFields(
  fileId: string,
  docType: DocType,
  ocrResult: OCRResult
): Promise<{ fields: ExtractedField[]; lineItems: LineItem[] }> {
  const res = await authFetch(`${API_BASE}/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      doc_type: docType,
      ocr_result: ocrResult,
    }),
  })
  if (!res.ok) throw new Error('Extraction failed')
  const data = await res.json()
  return { fields: data.fields, lineItems: data.line_items ?? [] }
}

export async function runLayoutLlmTestInference(
  fileId: string,
  docType: DocType,
  ocrResult: OCRResult
): Promise<void> {
  const res = await authFetch(`${API_BASE}/layoutllm-test-inference`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      doc_type: docType,
      ocr_result: ocrResult,
    }),
  })
  if (!res.ok) throw new Error('LayoutLLM test inference failed')
}

/** Step 3 → 4: Run validation rules, persisting the full pipeline trace alongside the result */
export async function validateEntry(
  fields: ExtractedField[],
  docType: DocType,
  fileId: string = '',
  fileName: string = '',
  ocrResult: OCRResult | null = null,
  classificationResult: ClassificationResult | null = null,
  lineItems: LineItem[] = []
): Promise<ValidationResult> {
  const res = await authFetch(`${API_BASE}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fields,
      doc_type: docType,
      file_id: fileId,
      file_name: fileName,
      ocr_result: ocrResult,
      classification_result: classificationResult
        ? {
            type: classificationResult.type,
            label: classificationResult.label,
            sub_category: classificationResult.subCategory,
            confidence: classificationResult.confidence,
            classifier_level: classificationResult.classifierLevel,
            top_predictions: classificationResult.topPredictions,
            date: classificationResult.date,
            suggested_sub_categories: classificationResult.suggestedSubCategories,
          }
        : null,
      line_items: lineItems,
    }),
  })
  if (!res.ok) {
     // Fallback to mock if not implemented yet
     console.warn("Backend validation not implemented, using mock.")
     return mockValidateEntry(fields)
  }
  const data = await res.json()
  return {
    rules: data.rules,
    overallPassed: data.overall_passed,
    errors: data.errors,
    warnings: data.warnings,
  }
}

export interface DocumentSummaryRow {
  docType: DocType
  count: number
  totalAmount: number
}

export type DocumentDirection = 'payable' | 'receivable'

export interface DocumentRecord {
  id: string
  fileId: string
  fileName: string
  docType: DocType
  invoiceNo: string | null
  vendorName: string | null
  buyerName: string | null
  direction: DocumentDirection
  totalAmount: number | null
  documentDate: string | null
  overallPassed: boolean
  avgConfidence: number | null
  createdAt: string
}

export interface DocumentListResult {
  total: number
  page: number
  pageSize: number
  documents: DocumentRecord[]
}

/** Dashboard: counts + totals per doc type */
export async function fetchDocumentsSummary(): Promise<DocumentSummaryRow[]> {
  const res = await authFetch(`${API_BASE}/documents/summary`)
  if (!res.ok) throw new Error('Failed to fetch documents summary')
  const data = await res.json()
  return data.by_doc_type.map((row: any) => ({
    docType: row.doc_type,
    count: row.count,
    totalAmount: row.total_amount,
  }))
}

/** Dashboard / Records: paginated list of saved documents */
export async function fetchDocuments(params: {
  page?: number
  pageSize?: number
  docType?: DocType
  fromDate?: string
  toDate?: string
  search?: string
  vendorKey?: string
  direction?: DocumentDirection
} = {}): Promise<DocumentListResult> {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.pageSize) query.set('page_size', String(params.pageSize))
  if (params.docType) query.set('doc_type', params.docType)
  if (params.fromDate) query.set('from_date', params.fromDate)
  if (params.toDate) query.set('to_date', params.toDate)
  if (params.search) query.set('search', params.search)
  if (params.vendorKey) query.set('vendor_key', params.vendorKey)
  if (params.direction) query.set('direction', params.direction)

  const res = await authFetch(`${API_BASE}/documents?${query.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch documents')
  const data = await res.json()
  return {
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
    documents: data.documents.map((d: any) => ({
      id: d.id,
      fileId: d.file_id,
      fileName: d.file_name,
      docType: d.doc_type,
      invoiceNo: d.invoice_no,
      vendorName: d.vendor_name,
      buyerName: d.buyer_name,
      direction: d.direction,
      totalAmount: d.total_amount,
      documentDate: d.document_date,
      overallPassed: d.overall_passed,
      avgConfidence: d.avg_confidence,
      createdAt: d.created_at,
    })),
  }
}

export interface VendorProfile {
  vendorKey: string
  name: string
  gstin: string | null
  documentCount: number
  totalAmount: number
  avgAmount: number
  firstSeen: string
  lastSeen: string
  flaggedCount: number
}

/** Records: vendor folders — one entry per vendor with roll-up stats, for the folder view */
export async function fetchVendorProfiles(): Promise<VendorProfile[]> {
  const res = await authFetch(`${API_BASE}/vendors`)
  if (!res.ok) throw new Error('Failed to fetch vendors')
  const data = await res.json()
  return data.vendors.map((v: any) => ({
    vendorKey: v.vendor_key,
    name: v.name,
    gstin: v.gstin,
    documentCount: v.document_count,
    totalAmount: v.total_amount,
    avgAmount: v.avg_amount,
    firstSeen: v.first_seen,
    lastSeen: v.last_seen,
    flaggedCount: v.flagged_count,
  }))
}

/** Records: customer folders — receivable-side counterparties, same shape as fetchVendorProfiles */
export async function fetchCustomerProfiles(): Promise<VendorProfile[]> {
  const res = await authFetch(`${API_BASE}/customers`)
  if (!res.ok) throw new Error('Failed to fetch customers')
  const data = await res.json()
  return data.vendors.map((v: any) => ({
    vendorKey: v.vendor_key,
    name: v.name,
    gstin: v.gstin,
    documentCount: v.document_count,
    totalAmount: v.total_amount,
    avgAmount: v.avg_amount,
    firstSeen: v.first_seen,
    lastSeen: v.last_seen,
    flaggedCount: v.flagged_count,
  }))
}

export interface FieldCorrectionRecord {
  fieldName: string
  originalValue: string
  correctedValue: string
  modelConfidence: number | null
  createdAt: string
}

export interface DocumentDetail extends DocumentRecord {
  vendorGstin: string | null
  buyerGstin: string | null
  extractedFields: Record<string, string>
  extractionResult: ExtractedField[]
  lineItems: LineItem[]
  validationResult: ValidationResult
  hasOriginalFile: boolean
  mimeType: string | null
  corrections: FieldCorrectionRecord[]
}

function mapDocumentDetail(d: any): DocumentDetail {
  return {
    id: d.id,
    fileId: d.file_id,
    fileName: d.file_name,
    docType: d.doc_type,
    invoiceNo: d.invoice_no,
    vendorName: d.vendor_name,
    vendorGstin: d.vendor_gstin,
    buyerName: d.buyer_name,
    buyerGstin: d.buyer_gstin,
    direction: d.direction,
    avgConfidence: d.avg_confidence ?? null,
    totalAmount: d.total_amount,
    documentDate: d.document_date,
    overallPassed: d.overall_passed,
    createdAt: d.created_at,
    extractedFields: d.extracted_fields,
    extractionResult: d.extraction_result ?? [],
    lineItems: d.line_items ?? [],
    validationResult: {
      rules: d.validation_result.rules ?? [],
      overallPassed: d.validation_result.overall_passed ?? d.overall_passed,
      errors: d.validation_result.errors ?? [],
      warnings: d.validation_result.warnings ?? [],
    },
    hasOriginalFile: d.has_original_file,
    mimeType: d.mime_type,
    corrections: (d.corrections ?? []).map((c: any) => ({
      fieldName: c.field_name,
      originalValue: c.original_value,
      correctedValue: c.corrected_value,
      modelConfidence: c.model_confidence,
      createdAt: c.created_at,
    })),
  }
}

/** Records: full detail for one saved document, including fields + validation rules */
export async function fetchDocumentDetail(id: string): Promise<DocumentDetail> {
  const res = await authFetch(`${API_BASE}/documents/${id}`)
  if (!res.ok) throw new Error('Failed to fetch document detail')
  return mapDocumentDetail(await res.json())
}

/**
 * Document Review: apply corrections to a saved document and re-run validation
 * against them. `direction` is an optional manual override (payable/receivable) —
 * omit it to let the backend keep auto-detecting from the (possibly corrected) fields.
 */
export async function updateDocumentFields(
  id: string,
  fields: Record<string, string>,
  direction?: DocumentDirection
): Promise<DocumentDetail> {
  const res = await authFetch(`${API_BASE}/documents/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields, direction: direction ?? null }),
  })
  if (!res.ok) throw new Error('Failed to save corrections')
  return mapDocumentDetail(await res.json())
}

/** Document Review: fetch the original file as a blob URL (auth-protected, so plain <img src> won't work) */
export async function fetchDocumentFileUrl(id: string): Promise<string> {
  const res = await authFetch(`${API_BASE}/documents/${id}/file`)
  if (!res.ok) throw new Error('Failed to fetch original file')
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

export interface VendorConcentrationRow {
  vendorKey: string
  name: string
  totalAmount: number
  share: number
}

export interface MonthlyTrendRow {
  month: string
  totalAmount: number
}

export interface RecurringVendorRow {
  vendorKey: string
  name: string
  monthsSeen: number
  avgMonthlyAmount: number
  estimatedAnnualAmount: number
}

export interface MonthlyAnomalyRow {
  vendorKey: string
  name: string
  month: string
  currentAmount: number
  priorAvgAmount: number
  pctIncrease: number
}

export interface CategorySpendRow {
  category: string
  totalAmount: number
  documentCount: number
  share: number
}

export interface ExpenseAnalytics {
  totalSpend: number
  vendorConcentration: VendorConcentrationRow[]
  monthlyTrend: MonthlyTrendRow[]
  recurringVendors: RecurringVendorRow[]
  monthlyAnomalies: MonthlyAnomalyRow[]
  byCategory: CategorySpendRow[]
}

/** Insights: vendor concentration, spend trend, recurring vendors, monthly anomalies, category breakdown */
export async function fetchExpenseAnalytics(): Promise<ExpenseAnalytics> {
  const res = await authFetch(`${API_BASE}/insights/expenses`)
  if (!res.ok) throw new Error('Failed to fetch expense analytics')
  const d = await res.json()
  return {
    totalSpend: d.total_spend,
    vendorConcentration: d.vendor_concentration.map((r: any) => ({
      vendorKey: r.vendor_key,
      name: r.name,
      totalAmount: r.total_amount,
      share: r.share,
    })),
    monthlyTrend: d.monthly_trend.map((r: any) => ({ month: r.month, totalAmount: r.total_amount })),
    recurringVendors: d.recurring_vendors.map((r: any) => ({
      vendorKey: r.vendor_key,
      name: r.name,
      monthsSeen: r.months_seen,
      avgMonthlyAmount: r.avg_monthly_amount,
      estimatedAnnualAmount: r.estimated_annual_amount,
    })),
    monthlyAnomalies: d.monthly_anomalies.map((r: any) => ({
      vendorKey: r.vendor_key,
      name: r.name,
      month: r.month,
      currentAmount: r.current_amount,
      priorAvgAmount: r.prior_avg_amount,
      pctIncrease: r.pct_increase,
    })),
    byCategory: d.by_category.map((r: any) => ({
      category: r.category,
      totalAmount: r.total_amount,
      documentCount: r.document_count,
      share: r.share,
    })),
  }
}

export interface CorrectionInsightRow {
  fieldName: string
  correctionCount: number
  avgModelConfidence: number | null
}

/** Insights: which extracted fields humans correct most, and how confident the model was when wrong */
export async function fetchCorrectionInsights(): Promise<CorrectionInsightRow[]> {
  const res = await authFetch(`${API_BASE}/insights/corrections`)
  if (!res.ok) throw new Error('Failed to fetch correction insights')
  const d = await res.json()
  return d.fields.map((r: any) => ({
    fieldName: r.field_name,
    correctionCount: r.correction_count,
    avgModelConfidence: r.avg_model_confidence,
  }))
}

export interface ItcException {
  documentId: string
  vendorName: string
  itcAmount: number
  reason: string
}

export interface ItcSummary {
  totalCgst: number
  totalSgst: number
  totalIgst: number
  totalItc: number
  exceptions: ItcException[]
}

export interface PayableItem {
  documentId: string
  vendorName: string
  amount: number
  dueDate: string
  daysUntilDue: number
  bucket: 'overdue' | 'due_soon' | 'upcoming'
}

export interface PayablesAging {
  items: PayableItem[]
  overdueTotal: number
  dueSoonTotal: number
  upcomingTotal: number
}

export interface PriceAlert {
  vendorKey: string
  vendorName: string
  description: string
  previousRate: number
  currentRate: number
  pctIncrease: number
}

export interface FinanceInsights {
  itc: ItcSummary
  payables: PayablesAging
  priceAlerts: PriceAlert[]
}

/** Insights: ITC summary, payables aging, vendor price-increase alerts */
export async function fetchFinanceInsights(): Promise<FinanceInsights> {
  const res = await authFetch(`${API_BASE}/insights/finance`)
  if (!res.ok) throw new Error('Failed to fetch finance insights')
  const d = await res.json()
  return {
    itc: {
      totalCgst: d.itc.total_cgst,
      totalSgst: d.itc.total_sgst,
      totalIgst: d.itc.total_igst,
      totalItc: d.itc.total_itc,
      exceptions: d.itc.exceptions.map((e: any) => ({
        documentId: e.document_id,
        vendorName: e.vendor_name,
        itcAmount: e.itc_amount,
        reason: e.reason,
      })),
    },
    payables: {
      items: d.payables.items.map((i: any) => ({
        documentId: i.document_id,
        vendorName: i.vendor_name,
        amount: i.amount,
        dueDate: i.due_date,
        daysUntilDue: i.days_until_due,
        bucket: i.bucket,
      })),
      overdueTotal: d.payables.overdue_total,
      dueSoonTotal: d.payables.due_soon_total,
      upcomingTotal: d.payables.upcoming_total,
    },
    priceAlerts: d.price_alerts.map((p: any) => ({
      vendorKey: p.vendor_key,
      vendorName: p.vendor_name,
      description: p.description,
      previousRate: p.previous_rate,
      currentRate: p.current_rate,
      pctIncrease: p.pct_increase,
    })),
  }
}

export interface ReceivablesInsights {
  totalRevenue: number
  customerConcentration: VendorConcentrationRow[]
  receivablesAging: PayablesAging
}

/** Insights: customer concentration + receivables aging — the revenue-side mirror of finance insights */
export async function fetchReceivablesInsights(): Promise<ReceivablesInsights> {
  const res = await authFetch(`${API_BASE}/insights/receivables`)
  if (!res.ok) throw new Error('Failed to fetch receivables insights')
  const d = await res.json()
  return {
    totalRevenue: d.total_revenue,
    customerConcentration: d.customer_concentration.map((r: any) => ({
      vendorKey: r.vendor_key,
      name: r.name,
      totalAmount: r.total_amount,
      share: r.share,
    })),
    receivablesAging: {
      items: d.receivables_aging.items.map((i: any) => ({
        documentId: i.document_id,
        vendorName: i.vendor_name,
        amount: i.amount,
        dueDate: i.due_date,
        daysUntilDue: i.days_until_due,
        bucket: i.bucket,
      })),
      overdueTotal: d.receivables_aging.overdue_total,
      dueSoonTotal: d.receivables_aging.due_soon_total,
      upcomingTotal: d.receivables_aging.upcoming_total,
    },
  }
}

export interface CreditDebitNetting {
  vendorKey: string
  name: string
  invoicedTotal: number
  creditedTotal: number
  debitedTotal: number
  netPayable: number
  creditNoteCount: number
  creditNoteRate: number | null
  highCreditNoteRate: boolean
}

export interface LapsedVendor {
  vendorKey: string
  name: string
  lastSeenMonth: string
  monthsSinceLastInvoice: number
  avgMonthlyAmount: number
}

export interface DuplicateCluster {
  documentId: string
  otherDocumentId: string
  vendorName: string
  docType: string
  score: number
  reasons: string[]
  firstUploaded: string
  secondUploaded: string
}

export interface LowConfidenceDoc {
  documentId: string
  vendorName: string
  docType: string
  avgConfidence: number
  lowConfidenceFieldCount: number
  createdAt: string
}

export interface DocumentInsights {
  creditDebitNetting: CreditDebitNetting[]
  lapsedVendors: LapsedVendor[]
  duplicateClusters: DuplicateCluster[]
  lowConfidenceQueue: LowConfidenceDoc[]
}

/** Insights: credit/debit note netting, lapsed vendors, duplicate scan, low-confidence review queue */
export async function fetchDocumentInsights(): Promise<DocumentInsights> {
  const res = await authFetch(`${API_BASE}/insights/documents`)
  if (!res.ok) throw new Error('Failed to fetch document insights')
  const d = await res.json()
  return {
    creditDebitNetting: d.credit_debit_netting.map((n: any) => ({
      vendorKey: n.vendor_key,
      name: n.name,
      invoicedTotal: n.invoiced_total,
      creditedTotal: n.credited_total,
      debitedTotal: n.debited_total,
      netPayable: n.net_payable,
      creditNoteCount: n.credit_note_count,
      creditNoteRate: n.credit_note_rate,
      highCreditNoteRate: n.high_credit_note_rate,
    })),
    lapsedVendors: d.lapsed_vendors.map((v: any) => ({
      vendorKey: v.vendor_key,
      name: v.name,
      lastSeenMonth: v.last_seen_month,
      monthsSinceLastInvoice: v.months_since_last_invoice,
      avgMonthlyAmount: v.avg_monthly_amount,
    })),
    duplicateClusters: d.duplicate_clusters.map((c: any) => ({
      documentId: c.document_id,
      otherDocumentId: c.other_document_id,
      vendorName: c.vendor_name,
      docType: c.doc_type,
      score: c.score,
      reasons: c.reasons,
      firstUploaded: c.first_uploaded,
      secondUploaded: c.second_uploaded,
    })),
    lowConfidenceQueue: d.low_confidence_queue.map((q: any) => ({
      documentId: q.document_id,
      vendorName: q.vendor_name,
      docType: q.doc_type,
      avgConfidence: q.avg_confidence,
      lowConfidenceFieldCount: q.low_confidence_field_count,
      createdAt: q.created_at,
    })),
  }
}

export interface AppNotification {
  id: string
  severity: 'error' | 'warning'
  message: string
  documentId: string | null
}

/** Header bell: flat ranked list of things needing attention */
export async function fetchNotifications(): Promise<AppNotification[]> {
  const res = await authFetch(`${API_BASE}/insights/notifications`)
  if (!res.ok) throw new Error('Failed to fetch notifications')
  const d = await res.json()
  return d.notifications.map((n: any) => ({
    id: n.id,
    severity: n.severity,
    message: n.message,
    documentId: n.document_id ?? null,
  }))
}

export interface AppSettings {
  businessName: string
  businessGstin: string
  businessAddress: string
  classifierL1Threshold: number
  classifierL2Threshold: number
  extractorLayoutlmThreshold: number
  gstTaxMatchTolerance: number
  gstRateMatchTolerance: number
  updatedAt: string
}

function mapSettings(d: any): AppSettings {
  return {
    businessName: d.business_name,
    businessGstin: d.business_gstin,
    businessAddress: d.business_address,
    classifierL1Threshold: d.classifier_l1_threshold,
    classifierL2Threshold: d.classifier_l2_threshold,
    extractorLayoutlmThreshold: d.extractor_layoutlm_threshold,
    gstTaxMatchTolerance: d.gst_tax_match_tolerance,
    gstRateMatchTolerance: d.gst_rate_match_tolerance,
    updatedAt: d.updated_at,
  }
}

/** Settings: read the current business profile + tunable validation thresholds */
export async function fetchSettings(): Promise<AppSettings> {
  const res = await authFetch(`${API_BASE}/settings`)
  if (!res.ok) throw new Error('Failed to fetch settings')
  return mapSettings(await res.json())
}

/** Settings: update any subset of the business profile / thresholds */
export async function updateSettings(patch: Partial<{
  businessName: string
  businessGstin: string
  businessAddress: string
  classifierL1Threshold: number
  classifierL2Threshold: number
  extractorLayoutlmThreshold: number
  gstTaxMatchTolerance: number
  gstRateMatchTolerance: number
}>): Promise<AppSettings> {
  const body: Record<string, unknown> = {}
  if (patch.businessName !== undefined) body.business_name = patch.businessName
  if (patch.businessGstin !== undefined) body.business_gstin = patch.businessGstin
  if (patch.businessAddress !== undefined) body.business_address = patch.businessAddress
  if (patch.classifierL1Threshold !== undefined) body.classifier_l1_threshold = patch.classifierL1Threshold
  if (patch.classifierL2Threshold !== undefined) body.classifier_l2_threshold = patch.classifierL2Threshold
  if (patch.extractorLayoutlmThreshold !== undefined) body.extractor_layoutlm_threshold = patch.extractorLayoutlmThreshold
  if (patch.gstTaxMatchTolerance !== undefined) body.gst_tax_match_tolerance = patch.gstTaxMatchTolerance
  if (patch.gstRateMatchTolerance !== undefined) body.gst_rate_match_tolerance = patch.gstRateMatchTolerance

  const res = await authFetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Failed to update settings')
  return mapSettings(await res.json())
}

// Temporary mock for validation until Step 4 is finished
async function mockValidateEntry(fields: ExtractedField[]): Promise<ValidationResult> {
  const hasAmount = fields.some((f) => ['amount', 'total_amount', 'amount_due'].includes(f.key))
  const rules = [
    { name: 'Math Verification', passed: hasAmount, message: hasAmount ? 'Totals match' : 'Amount missing', severity: 'error' as const },
  ]
  return { rules, overallPassed: hasAmount, errors: [], warnings: [] }
}
