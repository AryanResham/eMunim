import type { Capabilities, ClassificationResult, DocType, ExtractedField, ExtractionRun, Pipeline, ReviewPolicy, SavedDocument, ValidationResult } from '@/types/upload'
import type { OCRResult } from '@/types/ocr'

export const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API_BASE + path, options)
  if (!response.ok) {
    let message = response.statusText
    try { const data = await response.json(); message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail) } catch { /* retain status */ }
    throw new Error(message || 'Request failed')
  }
  return response.json()
}
export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
}
export const capabilities = () => request<Capabilities>('/capabilities')
export async function uploadFile(file: File) {
  const form = new FormData(); form.append('file', file)
  const uploaded = await request<{file_id:string; width:number; height:number}[]>('/upload', {method:'POST',body:form})
  return uploaded[0]
}
export const runOcr = (fileId: string) => post<OCRResult>('/ocr', {file_id:fileId})
export async function classifyDocument(fileId: string, ocrText: string): Promise<ClassificationResult> {
  const data = await post<{type:DocType; label:string; sub_category:string; confidence:number; classifier_level:'L1'|'L2'|'L3'; date:string; suggested_sub_categories:string[]; top_predictions?:{type:DocType;confidence:number}[]}>('/classify', {file_id:fileId,ocr_text:ocrText})
  return {type:data.type,label:data.label,subCategory:data.sub_category,confidence:data.confidence,classifierLevel:data.classifier_level,date:data.date,suggestedSubCategories:data.suggested_sub_categories,topPredictions:data.top_predictions}
}
export const validationResult = (data: ValidationResult & {overall_passed?:boolean}): ValidationResult => ({...data,overallPassed:data.overall_passed ?? data.overallPassed})
export async function extractFields(fileId:string,docType:DocType,ocrResult:OCRResult|null,pipeline:Pipeline='ocr_layoutlm',policy:ReviewPolicy='validation_review',businessRole:'buyer'|'vendor'='buyer'):Promise<ExtractionRun> {
  const data = await post<ExtractionRun>('/extract', {file_id:fileId,doc_type:docType,ocr_result:ocrResult,pipeline,review_policy:policy,classification_confirmed:true,business_role:businessRole})
  return {...data,validation:validationResult(data.validation)}
}
export async function validateEntry(fields:ExtractedField[],docType:DocType,policy:ReviewPolicy='validation_review',runId?:string):Promise<ValidationResult> {
  return validationResult(await post<ValidationResult>('/validate', {fields,doc_type:docType,policy,run_id:runId}))
}
export const saveDocument = (runId:string,fields:ExtractedField[],reason:string) => post<SavedDocument>('/documents', {run_id:runId,fields,confirmed:true,override_reason:reason})
export const listDocuments = (params:string='') => request<{items:SavedDocument[];total:number}>('/documents?'+params)
export const summary = () => request<{count:number;with_issues:number;by_type:Record<string,{count:number;printed_amount_total:string;amount_count:number}>;note:string}>('/documents/summary')
