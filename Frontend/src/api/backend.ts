import type {
  ClassificationResult,
  DocType,
  ExtractedField,
  ValidationResult,
} from '@/types/upload'
import type { OCRResult } from '@/types/ocr'

const API_BASE = 'http://localhost:8000/api'

/** Step 1 → 2: Classify the uploaded document using the real backend */
export async function classifyDocument(fileId: string, ocrText: string): Promise<ClassificationResult> {
  const res = await fetch(`${API_BASE}/classify`, {
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
    merchant: data.merchant,
    date: data.date,
    suggestedSubCategories: data.suggested_sub_categories,
    topPredictions: data.top_predictions?.map((p: any) => ({
      type: p.type,
      confidence: p.confidence,
    })),
  }
}

/** Step 2 → 3: Extract structured fields from the classified document */
export async function extractFields(
  fileId: string,
  docType: DocType,
  ocrResult: OCRResult
): Promise<ExtractedField[]> {
  const res = await fetch(`${API_BASE}/extract`, {
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
  return data.fields // Backend returns { fields: [...], line_items: [...] }
}

/** Step 3 → 4: Run validation rules (Keep mock for now as backend router isn't ready) */
export async function validateEntry(fields: ExtractedField[]): Promise<ValidationResult> {
  // We will connect this once we implement backend/routers/validate.py
  const res = await fetch(`${API_BASE}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields }), // Adjust based on final schema
  })
  if (!res.ok) {
     // Fallback to mock if not implemented yet
     console.warn("Backend validation not implemented, using mock.")
     return mockValidateEntry(fields)
  }
  return await res.json()
}

// Temporary mock for validation until Step 4 is finished
async function mockValidateEntry(fields: ExtractedField[]): Promise<ValidationResult> {
  const hasAmount = fields.some((f) => ['amount', 'total_amount', 'amount_due'].includes(f.key))
  const rules = [
    { name: 'Math Verification', passed: hasAmount, message: hasAmount ? 'Totals match' : 'Amount missing', severity: 'error' as const },
  ]
  return { rules, overallPassed: hasAmount, errors: [], warnings: [] }
}
