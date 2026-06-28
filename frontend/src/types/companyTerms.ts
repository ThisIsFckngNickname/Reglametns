// ---- Company Terms & Abbreviations types ----

export interface CompanyTerm {
  id: number
  company_id: number
  term: string
  definition: string
  source_document_id: number | null
  source_document_title: string | null
  is_manual: boolean
  created_at: string
  updated_at: string
}

export interface CompanyAbbreviation {
  id: number
  company_id: number
  abbreviation: string
  full_form: string
  source_document_id: number | null
  source_document_title: string | null
  is_manual: boolean
  created_at: string
  updated_at: string
}

export interface PaginatedTermsResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type DocumentType = 'regulation' | 'order' | 'provision' | 'policy' | 'directive'

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  regulation: 'Регламент',
  order: 'Приказ',
  provision: 'Положение',
  policy: 'Политика',
  directive: 'Распоряжение',
}

export const DOCUMENT_TYPE_OPTIONS = Object.entries(DOCUMENT_TYPE_LABELS).map(([value, label]) => ({
  value: value as DocumentType,
  label,
}))

export interface TermFormValues {
  term: string
  definition: string
}

export interface AbbreviationFormValues {
  abbreviation: string
  full_form: string
}
