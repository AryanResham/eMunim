import type { OCRResult } from './ocr'
export type DocType = 'GST_INVOICE' | 'PURCHASE_BILL' | 'EXPENSE_RECEIPT' | 'UTILITY_BILL' | 'CREDIT_NOTE' | 'DEBIT_NOTE'
export type Pipeline = 'ocr_layoutlm' | 'hosted_vlm' | 'layoutlm_hosted_fallback' | 'layoutlm_llm_vlm'
export type ReviewPolicy = 'extraction_only' | 'validation_review' | 'validation_confidence_review'
export interface ClassificationResult {
  type: DocType; label: string; subCategory: string; confidence: number
  classifierLevel: 'L1' | 'L2' | 'L3'; topPredictions?: {type: DocType; confidence: number}[]
  date: string; suggestedSubCategories: string[]
}
export interface ExtractedField {
  key: string; label: string; value: string | null; confidence: number | null
  editable: boolean; monospace?: boolean; source?: string
}
export interface ValidationRule {
  name: string; passed: boolean | null; message: string; severity: 'error' | 'warning'
  status?: string; fields?: string[]
}
export interface ValidationResult {
  rules: ValidationRule[]; overallPassed: boolean; errors: ValidationRule[]; warnings: ValidationRule[]
  review_required?: boolean; review_reasons?: string[]; flagged_fields?: string[]
  policy?: ReviewPolicy; threshold?: number | null
}
export interface ExtractionRun {
  run_id: string; file_id: string; doc_type: DocType; pipeline: Pipeline
  fields: ExtractedField[]; line_items: Record<string,string>[]; validation: ValidationResult
  metadata: {elapsed_ms: number; routing_reasons: string[]; conflicts: string[]; operational_reasons: string[];
    degraded: boolean; hosted: {model?: string; attempts: number; logical_calls: number; cached?: boolean; error?: string}
    hosted_llm?: {model?: string; attempts: number; logical_calls: number; cached?: boolean; error?: string}
    cascade?: {plan: {llm: string[]; vlm: string[]}; tiers: ('llm'|'vlm')[]; escalated: string[]}}
}
export interface SavedDocument {
  id: string; run_id: string; file_id: string; doc_type: DocType; pipeline: Pipeline; created_at: string
  fields: ExtractedField[]; original_fields: ExtractedField[]; line_items: Record<string,string>[]
  validation: ValidationResult; metadata: ExtractionRun['metadata']; status: string
  audit: {at: string; action: string; changes: {key: string; before: string|null; after: string|null}[]; reason: string}[]
}
export interface Capabilities {
  model_status?: { classifier: string; extractors: Record<string,string> }
  ocr_configured: boolean; hosted_configured: boolean; hosted_model: string|null
  hosted_llm_configured: boolean; hosted_llm_model: string|null
  layoutlm_weights_present: Record<DocType, boolean>; database: string; threshold_status: string
  review_threshold: number; fallback_threshold: number; max_upload_mb: number
}
export interface WorkflowState {
  step: 1|2|3|4; direction: 1|-1; file: File|null; fileId: string|null; filePreviewUrl: string|null
  classification: ClassificationResult|null; extractedFields: ExtractedField[]|null
  validationResult: ValidationResult|null; ocrResult: OCRResult|null; pipeline: Pipeline; vlmOnly: boolean
  processedWidth: number; processedHeight: number; isProcessing: boolean
}
