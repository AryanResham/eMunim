export interface DashboardMonth {
  month: string; documents: number
  in: number; out: number; adjustment: number; cgst: number; sgst: number; igst: number
}
export interface DashboardParty { name: string; amount: number; count: number }
export interface DashboardData {
  totals: {documents: number; needs_review: number; undated: number; corrected_documents: number
    billed_in: number; billed_out: number; adjustments: number}
  months: DashboardMonth[]
  by_type: {type: string; count: number; amount: number}[]
  top_vendors: DashboardParty[]
  top_customers: DashboardParty[]
  due: {id: string; doc_type: string; party: string|null; due_date: string; days: number; amount: number|null; direction: string}[]
  quality: {corrected_fields: {key: string; count: number}[]
    pipelines: {name: string; count: number; corrections: number; corrections_per_document: number}[]}
  note: string
}
