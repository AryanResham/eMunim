export type DocType = 'expense' | 'invoice' | 'payroll' | 'bank_statement'

export interface ClassificationResult {
  type: DocType
  label: string
  subCategory: string
  confidence: number
  merchant: string
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
}

export interface ValidationResult {
  rules: ValidationRule[]
  overallPassed: boolean
}

export interface WorkflowState {
  step: 1 | 2 | 3 | 4
  direction: 1 | -1
  file: File | null
  filePreviewUrl: string | null
  classification: ClassificationResult | null
  extractedFields: ExtractedField[] | null
  validationResult: ValidationResult | null
  isProcessing: boolean
}
