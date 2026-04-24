/**
 * Mock Backend — eMunim AI Document Processing
 *
 * All functions mirror the interface of a real API:
 * async, typed responses, realistic latency.
 * To connect a real backend, replace the bodies of these functions
 * with fetch() calls — no component code needs to change.
 */

import type {
  ClassificationResult,
  DocType,
  ExtractedField,
  ValidationResult,
} from '@/types/upload'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

function detectDocType(filename: string): DocType {
  const name = filename.toLowerCase()
  if (name.includes('credit')) return 'CREDIT_NOTE'
  if (name.includes('debit')) return 'DEBIT_NOTE'
  if (name.includes('utility') || name.includes('electric') || name.includes('water')) return 'UTILITY_BILL'
  if (name.includes('purchase') || name.includes('po') || name.includes('vendor')) return 'PURCHASE_BILL'
  if (name.includes('expense') || name.includes('receipt')) return 'EXPENSE_RECEIPT'
  return 'GST_INVOICE'
}

// ---------------------------------------------------------------------------
// Mock data pools
// ---------------------------------------------------------------------------

const CLASSIFICATIONS: Record<DocType, ClassificationResult> = {
  GST_INVOICE: {
    type: 'GST_INVOICE',
    label: 'GST Tax Invoice',
    subCategory: 'Accounts Payable',
    confidence: 99,
    classifierLevel: 'L1',
    date: 'Apr 5, 2026',
    suggestedSubCategories: ['Accounts Payable', 'Input Tax Credit', 'Supplier Invoice', 'Import Bill'],
  },
  PURCHASE_BILL: {
    type: 'PURCHASE_BILL',
    label: 'Purchase Bill',
    subCategory: 'Raw Materials',
    confidence: 87,
    classifierLevel: 'L2',
    date: 'Apr 8, 2026',
    suggestedSubCategories: ['Raw Materials', 'Office Supplies', 'Capital Goods', 'Trade Purchase'],
  },
  EXPENSE_RECEIPT: {
    type: 'EXPENSE_RECEIPT',
    label: 'Expense Receipt',
    subCategory: 'Software Subscription',
    confidence: 96,
    classifierLevel: 'L1',
    date: 'Apr 10, 2026',
    suggestedSubCategories: ['Software Subscription', 'Travel & Conveyance', 'Meals & Entertainment', 'Petrol & Fuel', 'Office Expenses'],
  },
  UTILITY_BILL: {
    type: 'UTILITY_BILL',
    label: 'Utility Bill',
    subCategory: 'Electricity',
    confidence: 94,
    classifierLevel: 'L1',
    date: 'Apr 1, 2026',
    suggestedSubCategories: ['Electricity', 'Water', 'Internet / Broadband', 'Telephone', 'Gas'],
  },
  CREDIT_NOTE: {
    type: 'CREDIT_NOTE',
    label: 'Credit Note',
    subCategory: 'Sales Return',
    confidence: 95,
    classifierLevel: 'L1',
    date: 'Apr 3, 2026',
    suggestedSubCategories: ['Sales Return', 'Discount Allowed', 'Price Adjustment'],
  },
  DEBIT_NOTE: {
    type: 'DEBIT_NOTE',
    label: 'Debit Note',
    subCategory: 'Purchase Return',
    confidence: 91,
    classifierLevel: 'L1',
    date: 'Apr 7, 2026',
    suggestedSubCategories: ['Purchase Return', 'Charge Back', 'Penalty'],
  },
}

const EXTRACTED_FIELDS: Record<DocType, ExtractedField[]> = {
  GST_INVOICE: [
    { key: 'invoice_no',    label: 'Invoice No.',      value: 'CB-INV-2026-1134',          confidence: 97, editable: false, monospace: true },
    { key: 'invoice_date',  label: 'Invoice Date',     value: 'Apr 5, 2026',                confidence: 99, editable: true },
    { key: 'vendor_name',   label: 'Vendor Name',      value: 'CloudBase Systems Pvt. Ltd.', confidence: 99, editable: true },
    { key: 'vendor_gstin',  label: 'Vendor GSTIN',     value: '27AABCU9603R1ZM',            confidence: 95, editable: false, monospace: true },
    { key: 'buyer_gstin',   label: 'Buyer GSTIN',      value: '27AAECS8895E1Z4',            confidence: 94, editable: false, monospace: true },
    { key: 'taxable_amount',label: 'Taxable Amount',   value: '₹28,500.00',                 confidence: 98, editable: true, monospace: true },
    { key: 'cgst_amount',   label: 'CGST (9%)',        value: '₹2,565.00',                  confidence: 95, editable: true, monospace: true },
    { key: 'sgst_amount',   label: 'SGST (9%)',        value: '₹2,565.00',                  confidence: 95, editable: true, monospace: true },
    { key: 'total_amount',  label: 'Total Amount',     value: '₹33,630.00',                 confidence: 99, editable: true, monospace: true },
  ],
  PURCHASE_BILL: [
    { key: 'bill_no',       label: 'Bill No.',         value: 'PB-2026-0421',               confidence: 92, editable: false, monospace: true },
    { key: 'bill_date',     label: 'Bill Date',        value: 'Apr 8, 2026',                confidence: 98, editable: true },
    { key: 'vendor_name',   label: 'Vendor Name',      value: 'Sharma Traders',             confidence: 97, editable: true },
    { key: 'vendor_gstin',  label: 'Vendor GSTIN',     value: '07AAEFS1234B1Z5',            confidence: 89, editable: false, monospace: true },
    { key: 'subtotal',      label: 'Subtotal',         value: '₹12,000.00',                 confidence: 96, editable: true, monospace: true },
    { key: 'tax_amount',    label: 'Tax',              value: '₹2,160.00',                  confidence: 93, editable: true, monospace: true },
    { key: 'total_amount',  label: 'Total',            value: '₹14,160.00',                 confidence: 97, editable: true, monospace: true },
  ],
  EXPENSE_RECEIPT: [
    { key: 'vendor_name',   label: 'Vendor',           value: 'Adobe Systems Inc.',         confidence: 99, editable: true },
    { key: 'receipt_date',  label: 'Date',             value: 'Apr 10, 2026',               confidence: 100, editable: true },
    { key: 'receipt_no',    label: 'Receipt No.',      value: 'INV-2026-00842',             confidence: 88, editable: false, monospace: true },
    { key: 'amount',        label: 'Amount',           value: '₹4,379.00',                  confidence: 97, editable: true, monospace: true },
    { key: 'tax_amount',    label: 'Tax (GST 18%)',    value: '₹663.00',                    confidence: 91, editable: true, monospace: true },
    { key: 'payment_mode',  label: 'Payment Mode',     value: 'Credit Card',                confidence: 85, editable: true },
  ],
  UTILITY_BILL: [
    { key: 'utility_provider', label: 'Provider',     value: 'MSEB / Adani Electricity',   confidence: 97, editable: true },
    { key: 'consumer_no',   label: 'Consumer No.',     value: 'MH-402-88321',               confidence: 99, editable: false, monospace: true },
    { key: 'bill_date',     label: 'Bill Date',        value: 'Apr 1, 2026',                confidence: 99, editable: true },
    { key: 'due_date',      label: 'Due Date',         value: 'Apr 15, 2026',               confidence: 98, editable: true },
    { key: 'units_consumed',label: 'Units Consumed',   value: '840 kWh',                    confidence: 95, editable: true, monospace: true },
    { key: 'amount_due',    label: 'Amount Due',       value: '₹6,720.00',                  confidence: 97, editable: true, monospace: true },
  ],
  CREDIT_NOTE: [
    { key: 'credit_note_no',    label: 'Credit Note No.', value: 'CN-2026-0089',            confidence: 96, editable: false, monospace: true },
    { key: 'credit_note_date',  label: 'Date',            value: 'Apr 3, 2026',             confidence: 99, editable: true },
    { key: 'original_invoice_no', label: 'Ref Invoice',   value: 'INV-2026-0312',           confidence: 91, editable: true, monospace: true },
    { key: 'vendor_name',       label: 'Vendor',          value: 'Mehta Distributors',      confidence: 98, editable: true },
    { key: 'vendor_gstin',      label: 'Vendor GSTIN',    value: '24AABCM4567F1Z3',         confidence: 93, editable: false, monospace: true },
    { key: 'credit_amount',     label: 'Credit Amount',   value: '₹5,000.00',               confidence: 97, editable: true, monospace: true },
    { key: 'tax_credit',        label: 'GST Reversal',    value: '₹900.00',                 confidence: 90, editable: true, monospace: true },
  ],
  DEBIT_NOTE: [
    { key: 'debit_note_no',    label: 'Debit Note No.',   value: 'DN-2026-0041',            confidence: 95, editable: false, monospace: true },
    { key: 'debit_note_date',  label: 'Date',             value: 'Apr 7, 2026',             confidence: 99, editable: true },
    { key: 'original_invoice_no', label: 'Ref Invoice',   value: 'PO-2026-0298',            confidence: 88, editable: true, monospace: true },
    { key: 'vendor_name',      label: 'Vendor',           value: 'National Suppliers Ltd.', confidence: 97, editable: true },
    { key: 'vendor_gstin',     label: 'Vendor GSTIN',     value: '29AABCN7890G1Z1',         confidence: 92, editable: false, monospace: true },
    { key: 'debit_amount',     label: 'Debit Amount',     value: '₹3,200.00',               confidence: 96, editable: true, monospace: true },
    { key: 'tax_amount',       label: 'Tax Amount',       value: '₹576.00',                 confidence: 91, editable: true, monospace: true },
  ],
}

// ---------------------------------------------------------------------------
// API functions — swap these bodies for real fetch() calls
// ---------------------------------------------------------------------------

/** Step 1 → 2: Classify the uploaded document */
export async function classifyDocument(file: File): Promise<ClassificationResult> {
  await delay(1800)
  const type = detectDocType(file.name)
  return CLASSIFICATIONS[type]
}

/** Step 2 → 3: Extract structured fields from the classified document */
export async function extractFields(classification: ClassificationResult): Promise<ExtractedField[]> {
  await delay(1400)
  return EXTRACTED_FIELDS[classification.type]
}

/** Step 3 → 4: Run validation rules on the extracted fields */
export async function validateEntry(fields: ExtractedField[]): Promise<ValidationResult> {
  await delay(800)

  const hasAmount = fields.some((f) => ['amount', 'total_amount', 'amount_due', 'credit_amount', 'debit_amount'].includes(f.key))
  const hasGstin = fields.some((f) => f.key === 'vendor_gstin')
  const hasTax = fields.some((f) => ['tax_amount', 'cgst_amount', 'sgst_amount'].includes(f.key))

  const rules = [
    {
      name: 'GST Calculation',
      passed: hasTax,
      message: hasTax ? 'Tax amount present and consistent' : 'No tax field found — verify manually',
      severity: hasTax ? 'warning' as const : 'warning' as const,
    },
    {
      name: 'Math Verification',
      passed: hasAmount,
      message: hasAmount ? 'All totals cross-check correctly' : 'Amount field missing — unable to verify',
      severity: 'error' as const,
    },
    {
      name: 'GSTIN Format',
      passed: hasGstin,
      message: hasGstin ? 'GSTIN format is valid' : 'GSTIN not found — required for GST compliance',
      severity: 'error' as const,
    },
    {
      name: 'Duplicate Check',
      passed: true,
      message: 'No duplicate entries found in the ledger',
      severity: 'warning' as const,
    },
  ]

  const errors = rules.filter((r) => !r.passed && r.severity === 'error')
  const warnings = rules.filter((r) => !r.passed && r.severity === 'warning')

  return {
    rules,
    overallPassed: errors.length === 0,
    errors,
    warnings,
  }
}
