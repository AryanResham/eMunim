import type { OCRResult } from '@/types/ocr'

export type DocType =
  | 'GST_INVOICE'
  | 'PURCHASE_BILL'
  | 'EXPENSE_RECEIPT'
  | 'UTILITY_BILL'
  | 'CREDIT_NOTE'
  | 'DEBIT_NOTE'

export interface ClassificationResult {
  type: DocType
  label: string
  subCategory: string
  confidence: number
  classifierLevel: 'L1' | 'L2' | 'L3'
  topPredictions?: { type: DocType; confidence: number }[]
  date: string
  suggestedSubCategories: string[]
}

export interface ExtractedField {
  key: string
  label: string
  value: string
  confidence: number
  editable: boolean
  monospace?: boolean
}

export interface ValidationRule {
  name: string
  passed: boolean
  message: string
  severity: 'error' | 'warning'
}

export interface ValidationResult {
  rules: ValidationRule[]
  overallPassed: boolean
  errors: ValidationRule[]
  warnings: ValidationRule[]
}

export interface WorkflowState {
  step: 1 | 2 | 3 | 4
  direction: 1 | -1
  file: File | null
  fileId: string | null
  filePreviewUrl: string | null
  classification: ClassificationResult | null
  extractedFields: ExtractedField[] | null
  validationResult: ValidationResult | null
  ocrResult: OCRResult | null
  processedWidth: number
  processedHeight: number
  isProcessing: boolean
}
