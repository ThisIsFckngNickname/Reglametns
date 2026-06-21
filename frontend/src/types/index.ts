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

export interface HoldingBrief {
  id: number
  name: string
  inn: string | null
  legal_form: string
}

export interface UserHoldingInfo {
  holding_id: number
  holding_name: string
  role: string
}

export interface UserProfile {
  id: number
  email: string
  is_verified: boolean
  active_holding: HoldingBrief | null
  holdings?: UserHoldingInfo[]
}

export interface SetHoldingRequest {
  holding_id: number
}

export interface SetHoldingResponse {
  message: string
  active_holding: {
    id: number
    name: string
  }
}

// ---- Holding types ----

export interface Holding {
  id: number
  name: string
  inn: string | null
  legal_form: string
  created_at: string
}

export interface HoldingCreate {
  name: string
  inn?: string | null
  legal_form: string
}

export interface HoldingUpdate {
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
  holding_id?: number | null
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
  active_holding: HoldingBrief | null
  holdings: UserHoldingInfo[]
  created_at: string
}

// ---- Document types ----

export type DocumentStatus = 'draft' | 'review' | 'approved' | 'archived'

export interface DocumentListItem {
  id: number
  title: string
  status: DocumentStatus
  file_type: 'docx' | 'pdf'
  file_size: number
  version_number: number
  current_version: DocumentVersionBrief | null
  has_terms: boolean
  has_abbreviations: boolean
  created_by: { id: number; email: string }
  created_at: string
  updated_at: string
}

export interface DocumentDetail {
  id: number
  title: string
  description: string | null
  status: DocumentStatus
  holding_id: number
  created_by: { id: number; email: string }
  current_version: DocumentVersionBrief | null
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

// ---- Holding Profile types ----

export interface AvailableSource {
  id: string // "pravo_gov_ru" | "docs_cntd_ru" | "consultant_plus" | "garant" | "user_defined"
  display_name: string
  description: string
  is_paid: boolean
  is_builtin: boolean
  is_active: boolean // входит ли в active_sources текущего холдинга
}

export interface HoldingProfile {
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
  source_document?: DocumentListItem
  target_document?: DocumentListItem
  created_at: string
}

// ---- Orders ----

export type OrderStatus = 'draft' | 'active' | 'cancelled'

export interface Order {
  id: number
  title: string
  order_number: string | null
  order_date: string | null
  description: string | null
  status: OrderStatus
  file_type: string | null
  file_size: number | null
  created_by: { id: number; email: string }
  created_at: string
  updated_at: string
}

export interface OrderDocumentLink {
  id: number
  order_id: number
  document_id: number
  link_type: string
  description: string | null
  document?: DocumentListItem
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

export interface LegislationResult {
  query: string
  source: string
  items: LegislationItem[]
  total: number
  page: number
}

export interface LegislationSource {
  id: number
  holding_id: number
  name: string
  source_type: 'template_url' | 'static_list' | 'custom_parser'
  url_template: string | null
  parser_type: 'html' | 'json' | 'xml' | 'text' | null
  selector: string | null
  is_active: boolean
  is_paid: boolean
  icon_url: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface LegislationSourceCreate {
  name: string
  source_type: 'template_url' | 'static_list' | 'custom_parser'
  url_template?: string
  parser_type?: string
  selector?: string
  is_paid?: boolean
  icon_url?: string
  description?: string
}

export interface LegislationSourceSearchResult {
  title: string
  url: string
  snippet: string
  date: string | null
}

// ---- Impact Map types ----

export interface ImpactMap {
  document_id: number
  document_title: string
  incoming: {
    orders: ImpactItem[]
    documents: ImpactItem[]
  }
  outgoing: {
    orders: ImpactItem[]
    documents: ImpactItem[]
  }
}

export interface ImpactItem {
  id: number
  title: string
  type: 'amends' | 'references' | 'supersedes' | 'related' | 'cancels'
  date?: string
}

// ---- Impact Graph types (for cytoscape visualization) ----

export interface ImpactGraphNode {
  id: string
  label: string
  type: 'document' | 'order'
  documentId?: number
  orderId?: number
}

export interface ImpactGraphEdge {
  source: string
  target: string
  label: string
  type: string
}

export interface ImpactGraph {
  nodes: ImpactGraphNode[]
  edges: ImpactGraphEdge[]
}

// ---- Document Diff types ----

export interface DocumentDiffChange {
  field: string
  old_value: string | null
  new_value: string | null
}

export interface DocumentDiffResponse {
  from_version: number
  to_version: number
  changes: DocumentDiffChange[]
}
