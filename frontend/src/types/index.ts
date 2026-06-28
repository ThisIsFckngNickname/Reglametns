// ---- Auth types ----

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

// RegisterResponse = TokenResponse — возвращает токены сразу
export interface RegisterResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in: number
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in: number
}

// ---- User types ----

export interface CompanyBrief {
  id: number
  name: string
  inn: string | null
  legal_form: string
}

export interface UserCompanyInfo {
  company_id: number
  company_name: string
  role: string
}

export interface UserProfile {
  id: number
  email: string
  is_verified: boolean
  active_company: CompanyBrief | null
  companies?: UserCompanyInfo[]
}

export interface SetCompanyRequest {
  company_id: number
}

export interface SetCompanyResponse {
  message: string
  active_company: {
    id: number
    name: string
  }
}

// ---- Company types ----

export interface Company {
  id: number
  name: string
  inn: string | null
  legal_form: string
  created_at: string
}

export interface CompanyCreate {
  name: string
  inn?: string | null
  legal_form: string
}

export interface CompanyUpdate {
  name?: string
  inn?: string | null
  legal_form?: string
}

// ---- Error types ----

export interface ApiErrorDetail {
  code: string
  message: string
  field: string | null
}

export interface ApiError {
  detail: ApiErrorDetail
}

// ---- Auth state ----

export interface AuthState {
  accessToken: string | null
  user: UserProfile | null
  isAuthenticated: boolean
  isLoading: boolean

  setTokens: (access: string) => void
  setUser: (user: UserProfile) => void
  logout: () => void
}

// ---- Admin types ----

export interface AdminUserCreate {
  email: string
  password: string
  company_id?: number | null
  role?: string
}

export interface AdminUserUpdate {
  email?: string
  password?: string
  is_verified?: boolean
}

export interface AdminUserResponse {
  id: number
  email: string
  is_verified: boolean
  is_banned: boolean
  active_company: CompanyBrief | null
  companies: UserCompanyInfo[]
  created_at: string
}

// ---- Document types ----

export type DocumentStatus = 'draft' | 'review' | 'approved' | 'cancelled' | 'archived'

export interface DocumentListItem {
  id: number
  title: string
  description?: string | null
  status: DocumentStatus
  file_type?: string | null
  file_size?: number | null
  version_number?: number | null
  current_version?: DocumentVersionBrief | null
  has_terms?: boolean
  has_abbreviations?: boolean
  was_analyzed?: boolean
  created_by?: { id: number; email: string } | null
  created_at: string
  updated_at: string
}

export interface DocumentDetail {
  id: number
  title: string
  description: string | null
  status: DocumentStatus
  company_id: number
  created_by: { id: number; email: string }
  current_version: DocumentVersionBrief | null
  was_analyzed?: boolean
  stats: {
    sections_count: number
    tables_count: number
    terms_count: number
    abbreviations_count: number
    versions_count: number
  }
  created_at: string
  updated_at: string
}

export interface DocumentVersionBrief {
  id: number
  version_number: number
  file_type: string
  file_size: number
  created_at: string
}

export interface DocumentVersion {
  id: number
  version_number: number
  file_type: string
  file_size: number
  uploaded_by: { id: number; email: string }
  sections_count: number
  tables_count: number
  version_notes: string | null
  created_at: string
}

export interface DocumentSection {
  id: number
  title: string
  level: number
  order_num: number
  content: string | null
  children: DocumentSection[]
}

export interface DocumentTerm {
  id: number
  term: string
  definition: string
}

export interface DocumentAbbreviation {
  id: number
  abbreviation: string
  full_form: string
}

export interface DocumentTable {
  id: number
  caption: string | null
  section_title: string | null
  order_num: number
  rows_count: number | null
  cols_count: number | null
  html_content: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface UploadResponse {
  id: number
  title: string
  status: DocumentStatus
  file_type: string
  file_size: number
  sections_count: number
  tables_count: number
  terms_count: number
  abbreviations_count: number
  created_at: string
}

// ---- Generator types ----

export interface GenerateRequest {
  context: string
  draft_file_ids?: number[]
  influencing_document_ids?: number[]
}

export interface GenerateResponse {
  id: number
  title: string
  status: DocumentStatus
  file_type: 'docx'
  file_size: number
  current_version: DocumentVersionBrief
  generated_with_mock?: boolean
  created_at: string
}

export interface GeneratorState {
  step: 'form' | 'preparing' | 'generating' | 'formatting' | 'done' | 'error'
  progress: number  // 0-100
  message: string
  result: GenerateResponse | null
  error: string | null
}

// ---- Company Profile types ----

export interface AvailableSource {
  id: string // "pravo_gov_ru" | "docs_cntd_ru" | "consultant_plus" | "garant" | "user_defined"
  display_name: string
  description: string
  is_paid: boolean
  is_builtin: boolean
  is_active: boolean // входит ли в active_sources текущей компании
}

export interface CompanyProfile {
  id: number
  name: string
  inn: string | null
  legal_form: string
  active_sources: string[]
  available_sources?: AvailableSource[]
}

// ---- Document Links ----

export interface DocumentLink {
  id: number
  source_document_id: number
  target_document_id: number
  link_type: 'references' | 'amends' | 'supersedes' | 'related'
  is_manual: boolean
  description: string | null
  created_by: number | null
  created_at: string
  // Flat fields for outgoing links (from GET /documents/{id}/links)
  target_title?: string
  target_status?: string
  // Flat fields for incoming links (from GET /documents/{id}/links/incoming)
  source_title?: string
  source_status?: string
}

// ---- Legislation types ----

export interface LegislationItem {
  title: string
  number: string | null
  date: string | null
  source: string
  url: string
  snippet: string
}

