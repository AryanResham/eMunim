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
  if (name.includes('payroll') || name.includes('salary') || name.includes('wages')) return 'payroll'
  if (name.includes('inv') || name.includes('invoice') || name.includes('bill')) return 'invoice'
  if (name.includes('bank') || name.includes('statement') || name.includes('ledger')) return 'bank_statement'
  return 'expense'
}

// ---------------------------------------------------------------------------
// Mock data pools
// ---------------------------------------------------------------------------

const CLASSIFICATIONS: Record<DocType, ClassificationResult> = {
  expense: {
    type: 'expense',
    label: 'Expense Receipt',
    subCategory: 'Software Subscription',
    confidence: 96,
    merchant: 'Adobe Systems Inc.',
    date: 'Apr 10, 2026',
    suggestedSubCategories: [
      'Software Subscription',
      'Utility',
      'Petrol & Fuel',
      'Employee Travel',
      'Meals & Entertainment',
      'Office Supplies',
    ],
  },
  invoice: {
    type: 'invoice',
    label: 'Vendor Invoice',
    subCategory: 'Accounts Payable',
    confidence: 99,
    merchant: 'CloudBase Systems Pvt. Ltd.',
    date: 'Apr 5, 2026',
    suggestedSubCategories: [
      'Accounts Payable',
      'Consulting Services',
      'IT Infrastructure',
      'Marketing',
      'Legal & Compliance',
    ],
  },
  payroll: {
    type: 'payroll',
    label: 'Payroll Summary',
    subCategory: 'Employee Payroll',
    confidence: 100,
    merchant: 'Internal Payroll',
    date: 'Mar 31, 2026',
    suggestedSubCategories: [
      'Employee Payroll',
      'Contractor Payments',
      'Reimbursements',
      'Bonuses & Incentives',
    ],
  },
  bank_statement: {
    type: 'bank_statement',
    label: 'Bank Statement',
    subCategory: 'Current Account',
    confidence: 98,
    merchant: 'HDFC Bank Ltd.',
    date: 'Mar 31, 2026',
    suggestedSubCategories: [
      'Current Account',
      'Savings Account',
      'Credit Card Statement',
      'Loan Statement',
    ],
  },
}

const EXTRACTED_FIELDS: Record<DocType, ExtractedField[]> = {
  expense: [
    { key: 'vendor', label: 'Vendor', value: 'Adobe Systems Inc.', confidence: 99, editable: true },
    { key: 'amount', label: 'Amount', value: '₹4,379.00', confidence: 97, editable: true, monospace: true },
    { key: 'date', label: 'Date', value: 'Apr 10, 2026', confidence: 100, editable: true },
    { key: 'category', label: 'Category', value: 'Software Subscription', confidence: 95, editable: true },
    { key: 'gst', label: 'Tax (GST 18%)', value: '₹663.00', confidence: 91, editable: true, monospace: true },
    { key: 'invoice_no', label: 'Invoice #', value: 'INV-2026-00842', confidence: 88, editable: false, monospace: true },
  ],
  invoice: [
    { key: 'vendor', label: 'Vendor', value: 'CloudBase Systems Pvt. Ltd.', confidence: 99, editable: true },
    { key: 'invoice_no', label: 'Invoice #', value: 'CB-INV-2026-1134', confidence: 97, editable: false, monospace: true },
    { key: 'due_date', label: 'Due Date', value: 'Apr 19, 2026', confidence: 96, editable: true },
    { key: 'subtotal', label: 'Subtotal', value: '₹28,500.00', confidence: 98, editable: true, monospace: true },
    { key: 'tax', label: 'GST (18%)', value: '₹5,130.00', confidence: 95, editable: true, monospace: true },
    { key: 'total', label: 'Total', value: '₹33,630.00', confidence: 99, editable: true, monospace: true },
  ],
  payroll: [
    { key: 'period', label: 'Pay Period', value: 'Mar 1 – Mar 31, 2026', confidence: 100, editable: true },
    { key: 'employees', label: 'Employees', value: '12', confidence: 100, editable: false, monospace: true },
    { key: 'gross', label: 'Gross Pay', value: '₹14,25,000.00', confidence: 99, editable: true, monospace: true },
    { key: 'deductions', label: 'Deductions (PF + PT)', value: '₹1,71,000.00', confidence: 95, editable: true, monospace: true },
    { key: 'net', label: 'Net Pay', value: '₹12,54,000.00', confidence: 99, editable: true, monospace: true },
    { key: 'tds', label: 'TDS Deducted', value: '₹89,500.00', confidence: 92, editable: true, monospace: true },
  ],
  bank_statement: [
    { key: 'account_no', label: 'Account No.', value: 'XXXX XXXX 4829', confidence: 100, editable: false, monospace: true },
    { key: 'period', label: 'Statement Period', value: 'Mar 1 – Mar 31, 2026', confidence: 100, editable: true },
    { key: 'opening', label: 'Opening Balance', value: '₹8,42,315.50', confidence: 99, editable: false, monospace: true },
    { key: 'credits', label: 'Total Credits', value: '₹22,18,900.00', confidence: 98, editable: false, monospace: true },
    { key: 'debits', label: 'Total Debits', value: '₹19,87,240.00', confidence: 98, editable: false, monospace: true },
    { key: 'closing', label: 'Closing Balance', value: '₹10,73,975.50', confidence: 99, editable: false, monospace: true },
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

  const hasAmount = fields.some((f) => f.key === 'amount' || f.key === 'total')
  const hasGst = fields.some((f) => f.key === 'gst' || f.key === 'tax')

  const rules = [
    {
      name: 'GST Calculation',
      passed: hasGst,
      message: hasGst
        ? 'Tax amount matches 18% of base value'
        : 'No tax field found — please verify manually',
    },
    {
      name: 'Math Verification',
      passed: hasAmount,
      message: hasAmount
        ? 'All totals cross-check correctly'
        : 'Amount field missing — unable to verify',
    },
    {
      name: 'Duplicate Check',
      passed: true,
      message: 'No duplicate entries found in the ledger',
    },
  ]

  return {
    rules,
    overallPassed: rules.every((r) => r.passed),
  }
}
