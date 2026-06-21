import { http, HttpResponse, delay } from 'msw'

// In-memory state for mocks
let users: Record<string, { id: number; email: string; is_verified: boolean; active_company_id: number | null }> = {}
let verificationCodes: Array<{
  email: string
  code: string
  purpose: string
  expires_at: Date
  used: boolean
}> = []
let companies: Array<{
  id: number
  name: string
  inn: string | null
  legal_form: string
  active_sources: string[]
  created_at: string
}> = []
let userCompanies: Array<{
  user_id: number
  company_id: number
  role: string
}> = []
let nextUserId = 1
let nextCompanyId = 1
let nextCodeId = 1

// Built-in adapter sources registry
const BUILT_IN_SOURCES = [
  {
    id: 'pravo_gov_ru',
    display_name: 'Pravo.gov.ru',
    description: 'Официальный интернет-портал правовой информации',
    is_paid: false,
    is_builtin: true,
  },
  {
    id: 'docs_cntd_ru',
    display_name: 'Техэксперт (docs.cntd.ru)',
    description: 'Электронный фонд нормативных документов',
    is_paid: false,
    is_builtin: true,
  },
  {
    id: 'consultant_plus',
    display_name: 'Консультант+',
    description: 'Профессиональная справочная правовая система',
    is_paid: true,
    is_builtin: true,
  },
  {
    id: 'garant',
    display_name: 'Гарант',
    description: 'Справочная правовая система',
    is_paid: true,
    is_builtin: true,
  },
]

// In-memory state for document links
let documentLinks: Array<{
  id: number
  source_document_id: number
  target_document_id: number
  link_type: 'references' | 'amends' | 'supersedes' | 'related'
  is_manual: boolean
  description: string | null
  created_by: { id: number; email: string }
  created_at: string
}> = []
let nextLinkId = 1

// In-memory state for document versions (richer)
let documentVersionsList: Array<{
  id: number
  document_id: number
  version_number: number
  file_type: string
  file_size: number
  uploaded_by: { id: number; email: string }
  sections_count: number
  tables_count: number
  version_notes: string | null
  created_at: string
}> = []

function seedDocumentVersions() {
  documentVersionsList = [
    { id: 1, document_id: 1, version_number: 1, file_type: 'docx', file_size: 240000, uploaded_by: { id: 1, email: 'user@example.com' }, sections_count: 6, tables_count: 2, version_notes: 'Первоначальная версия', created_at: '2026-06-01T08:00:00Z' },
    { id: 2, document_id: 1, version_number: 2, file_type: 'docx', file_size: 248000, uploaded_by: { id: 1, email: 'user@example.com' }, sections_count: 7, tables_count: 3, version_notes: 'Добавлен раздел 2.3', created_at: '2026-06-10T09:00:00Z' },
    { id: 3, document_id: 1, version_number: 3, file_type: 'docx', file_size: 256000, uploaded_by: { id: 1, email: 'user@example.com' }, sections_count: 8, tables_count: 3, version_notes: 'Финальная версия после согласования', created_at: '2026-06-15T10:00:00Z' },
    { id: 4, document_id: 2, version_number: 1, file_type: 'pdf', file_size: 5120000, uploaded_by: { id: 1, email: 'user@example.com' }, sections_count: 5, tables_count: 2, version_notes: null, created_at: '2026-06-18T14:00:00Z' },
    { id: 5, document_id: 3, version_number: 1, file_type: 'docx', file_size: 128000, uploaded_by: { id: 1, email: 'user@example.com' }, sections_count: 4, tables_count: 1, version_notes: null, created_at: '2026-06-20T09:00:00Z' },
    { id: 6, document_id: 4, version_number: 1, file_type: 'pdf', file_size: 3800000, uploaded_by: { id: 1, email: 'user@example.com' }, sections_count: 5, tables_count: 3, version_notes: 'Первая версия', created_at: '2026-04-01T08:00:00Z' },
    { id: 7, document_id: 4, version_number: 2, file_type: 'pdf', file_size: 3840000, uploaded_by: { id: 1, email: 'user@example.com' }, sections_count: 6, tables_count: 4, version_notes: 'Обновление по результатам аудита', created_at: '2026-05-01T12:00:00Z' },
  ]
  versionsNextId = 11
}
seedDocumentVersions()

function seedDocumentLinks() {
  documentLinks = [
    { id: 1, source_document_id: 1, target_document_id: 4, link_type: 'references', is_manual: true, description: 'Ссылка на регламент аудита', created_by: { id: 1, email: 'user@example.com' }, created_at: '2026-06-16T10:00:00Z' },
    { id: 2, source_document_id: 2, target_document_id: 1, link_type: 'related', is_manual: true, description: 'Связан с основным регламентом', created_by: { id: 1, email: 'user@example.com' }, created_at: '2026-06-19T10:00:00Z' },
  ]
  nextLinkId = 3
}
seedDocumentLinks()



// Seed some demo data
function seedData() {
  companies = [
    { id: 1, name: 'Холдинг-Центр', inn: '7701123456', legal_form: 'ООО', active_sources: ['pravo_gov_ru', 'docs_cntd_ru'], created_at: new Date().toISOString() },
    { id: 2, name: 'Технопарк', inn: '7702987654', legal_form: 'АО', active_sources: ['pravo_gov_ru'], created_at: new Date().toISOString() },
    { id: 3, name: 'Инновации Будущего', inn: null, legal_form: 'ПАО', active_sources: [], created_at: new Date().toISOString() },
  ]
  nextCompanyId = 4
}
seedData()

// ---- Document mock types and state ----
type DocumentMockStatus = 'draft' | 'review' | 'approved' | 'archived'

interface DocumentMock {
  id: number
  title: string
  description: string | null
  status: DocumentMockStatus
  company_id: number
  created_by: { id: number; email: string }
  current_version: {
    id: number
    version_number: number
    file_type: string
    file_size: number
    created_at: string
  } | null
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

let documents: DocumentMock[] = [
  {
    id: 1,
    title: 'Регламент разработки внутренних нормативных документов',
    description: 'Настоящий регламент определяет порядок разработки, согласования и утверждения внутренних нормативных документов холдинга.',
    status: 'approved',
    company_id: 1,
    created_by: { id: 1, email: 'user@example.com' },
    current_version: { id: 1, version_number: 3, file_type: 'docx', file_size: 256000, created_at: '2026-06-15T10:00:00Z' },
    stats: { sections_count: 8, tables_count: 3, terms_count: 12, abbreviations_count: 5, versions_count: 3 },
    created_at: '2026-06-01T08:00:00Z',
    updated_at: '2026-06-15T10:00:00Z',
  },
  {
    id: 2,
    title: 'Инструкция по работе с системой электронного документооборота',
    description: null,
    status: 'review',
    company_id: 1,
    created_by: { id: 1, email: 'user@example.com' },
    current_version: { id: 2, version_number: 1, file_type: 'pdf', file_size: 5120000, created_at: '2026-06-18T14:00:00Z' },
    stats: { sections_count: 5, tables_count: 2, terms_count: 8, abbreviations_count: 3, versions_count: 1 },
    created_at: '2026-06-18T14:00:00Z',
    updated_at: '2026-06-18T14:00:00Z',
  },
  {
    id: 3,
    title: 'Политика конфиденциальности и обработки персональных данных',
    description: 'Документ определяет порядок сбора, хранения и обработки персональных данных сотрудников и контрагентов.',
    status: 'draft',
    company_id: 1,
    created_by: { id: 1, email: 'user@example.com' },
    current_version: { id: 3, version_number: 1, file_type: 'docx', file_size: 128000, created_at: '2026-06-20T09:00:00Z' },
    stats: { sections_count: 4, tables_count: 1, terms_count: 0, abbreviations_count: 0, versions_count: 1 },
    created_at: '2026-06-20T09:00:00Z',
    updated_at: '2026-06-20T09:00:00Z',
  },
  {
    id: 4,
    title: 'Регламент проведения внутреннего аудита',
    description: 'Порядок проведения плановых и внеплановых внутренних аудитов в подразделениях холдинга.',
    status: 'archived',
    company_id: 1,
    created_by: { id: 1, email: 'user@example.com' },
    current_version: { id: 4, version_number: 2, file_type: 'pdf', file_size: 3840000, created_at: '2026-05-01T12:00:00Z' },
    stats: { sections_count: 6, tables_count: 4, terms_count: 15, abbreviations_count: 7, versions_count: 2 },
    created_at: '2026-04-01T08:00:00Z',
    updated_at: '2026-05-01T12:00:00Z',
  },
]
let nextDocumentId = 5
let versionsNextId = 10

// In-memory state for legislation sources
let legislationSources: Array<{
  id: number
  company_id: number
  name: string
  source_type: 'template_url' | 'static_list' | 'custom_parser'
  url_template: string | null
  parser_type: string | null
  selector: string | null
  is_active: boolean
  is_paid: boolean
  icon_url: string | null
  description: string | null
  created_at: string
  updated_at: string
}> = [
  {
    id: 1,
    company_id: 1,
    name: 'Pravo.gov.ru',
    source_type: 'template_url',
    url_template: 'http://pravo.gov.ru/proxy/ips/?search={query}',
    parser_type: 'html',
    selector: '.document-item',
    is_active: true,
    is_paid: false,
    icon_url: null,
    description: 'Официальный интернет-портал правовой информации',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-06-01T08:00:00Z',
  },
  {
    id: 2,
    company_id: 1,
    name: 'Docs.cntd.ru',
    source_type: 'template_url',
    url_template: 'https://docs.cntd.ru/search?q={query}',
    parser_type: 'html',
    selector: '.search-result-item',
    is_active: true,
    is_paid: false,
    icon_url: null,
    description: 'Электронный фонд нормативных документов',
    created_at: '2026-02-20T12:00:00Z',
    updated_at: '2026-05-15T14:00:00Z',
  },
  {
    id: 3,
    company_id: 1,
    name: 'Консультант+',
    source_type: 'static_list',
    url_template: null,
    parser_type: null,
    selector: null,
    is_active: true,
    is_paid: true,
    icon_url: null,
    description: 'Профессиональная справочная правовая система',
    created_at: '2026-03-10T09:00:00Z',
    updated_at: '2026-06-10T11:00:00Z',
  },
]
let nextLegislationSourceId = 4

function generateCode(): string {
  return String(Math.floor(100000 + Math.random() * 900000))
}

function findUserByEmail(email: string) {
  return users[email.toLowerCase()] || null
}

function isCodeExpired(code: typeof verificationCodes[0]): boolean {
  return new Date() > new Date(code.expires_at)
}

// Build impact graph from impact map data
function buildImpactGraphFromMap(id: number, map: any) {
  const docId = `doc-${id}`
  const nodes: any[] = [{ id: docId, label: map.document_title, type: 'document', documentId: id }]
  const edges: any[] = []
  const seen = new Set<string>([docId])

  // Incoming documents
  for (const item of map.incoming.documents) {
    const nodeId = `doc-${item.id}`
    if (!seen.has(nodeId)) {
      nodes.push({ id: nodeId, label: item.title, type: 'document', documentId: item.id })
      seen.add(nodeId)
    }
    edges.push({ source: nodeId, target: docId, label: item.type, type: item.type })
  }
  // Outgoing documents
  for (const item of map.outgoing.documents) {
    const nodeId = `doc-${item.id}`
    if (!seen.has(nodeId)) {
      nodes.push({ id: nodeId, label: item.title, type: 'document', documentId: item.id })
      seen.add(nodeId)
    }
    edges.push({ source: docId, target: nodeId, label: item.type, type: item.type })
  }

  return { nodes, edges }
}

// Build available sources list for a company (built-in + user-defined)
function buildAvailableSources(companyId: number, activeSourceIds: string[]) {
  // User-defined sources for this company
  const userSources = legislationSources
    .filter((s) => s.company_id === companyId)
    .map((s) => ({
      id: `user_${s.id}`,
      display_name: s.name,
      description: s.description || '',
      is_paid: s.is_paid,
      is_builtin: false,
      is_active: activeSourceIds.includes(`user_${s.id}`),
    }))

  // Built-in sources
  const builtIn = BUILT_IN_SOURCES.map((s) => ({
    ...s,
    is_active: activeSourceIds.includes(s.id),
  }))

  return [...builtIn, ...userSources]
}

export const handlers = [
  // ---- Auth: Register ----
  http.post('/api/v1/auth/register', async ({ request }) => {
    await delay(300)
    const body = (await request.json()) as { email: string }
    const email = body.email.toLowerCase().trim()

    const existingUser = findUserByEmail(email)
    if (existingUser && existingUser.is_verified) {
      return HttpResponse.json(
        {
          detail: {
            code: 'CONFLICT',
            message: 'A user with this email already exists',
            field: 'email',
          },
        },
        { status: 409 }
      )
    }

    // Create or update user
    if (!existingUser) {
      users[email] = { id: nextUserId++, email, is_verified: false, active_company_id: null }
    }

    // Generate and store code
    const code = generateCode()
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000)
    verificationCodes.push({
      email,
      code,
      purpose: 'registration',
      expires_at: expiresAt,
      used: false,
    })

    console.log(`[MSW MOCK EMAIL] To: ${email} | Code: ${code} | Purpose: registration`)

    return HttpResponse.json(
      { message: 'Verification code sent to email', code_length: 6 },
      { status: 201 }
    )
  }),

  // ---- Auth: Verify Registration ----
  http.post('/api/v1/auth/verify-registration', async ({ request }) => {
    await delay(300)
    const body = (await request.json()) as { email: string; code: string }
    const email = body.email.toLowerCase().trim()

    const user = findUserByEmail(email)
    if (!user) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'User not found', field: 'email' } },
        { status: 404 }
      )
    }

    const codes = verificationCodes
      .filter((c) => c.email === email && c.purpose === 'registration' && !c.used)
      .sort((a, b) => new Date(b.expires_at).getTime() - new Date(a.expires_at).getTime())

    if (codes.length === 0) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Invalid verification code', field: 'code' } },
        { status: 400 }
      )
    }

    const latestCode = codes[0]
    if (latestCode.code !== body.code) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Invalid verification code', field: 'code' } },
        { status: 400 }
      )
    }

    if (isCodeExpired(latestCode)) {
      return HttpResponse.json(
        { detail: { code: 'CODE_EXPIRED', message: 'Verification code has expired', field: 'code' } },
        { status: 400 }
      )
    }

    latestCode.used = true
    users[email].is_verified = true

    return HttpResponse.json({ message: 'Email verified successfully', verified: true })
  }),

  // ---- Auth: Login ----
  http.post('/api/v1/auth/login', async ({ request }) => {
    await delay(300)
    const body = (await request.json()) as { email: string }
    const email = body.email.toLowerCase().trim()

    const user = findUserByEmail(email)
    if (!user) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'User not found', field: 'email' } },
        { status: 404 }
      )
    }

    if (!user.is_verified) {
      return HttpResponse.json(
        { detail: { code: 'FORBIDDEN', message: 'Email not verified', field: 'email' } },
        { status: 403 }
      )
    }

    const code = generateCode()
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000)
    verificationCodes.push({
      email,
      code,
      purpose: 'login',
      expires_at: expiresAt,
      used: false,
    })

    console.log(`[MSW MOCK EMAIL] To: ${email} | Code: ${code} | Purpose: login`)

    return HttpResponse.json({ message: 'Verification code sent to email' })
  }),

  // ---- Auth: Verify Login ----
  http.post('/api/v1/auth/verify-login', async ({ request }) => {
    await delay(300)
    const body = (await request.json()) as { email: string; code: string }
    const email = body.email.toLowerCase().trim()

    const user = findUserByEmail(email)
    if (!user) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'User not found', field: 'email' } },
        { status: 404 }
      )
    }

    const codes = verificationCodes
      .filter((c) => c.email === email && c.purpose === 'login' && !c.used)
      .sort((a, b) => new Date(b.expires_at).getTime() - new Date(a.expires_at).getTime())

    if (codes.length === 0) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Invalid verification code', field: 'code' } },
        { status: 400 }
      )
    }

    const latestCode = codes[0]
    if (latestCode.code !== body.code) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Invalid verification code', field: 'code' } },
        { status: 400 }
      )
    }

    if (isCodeExpired(latestCode)) {
      return HttpResponse.json(
        { detail: { code: 'CODE_EXPIRED', message: 'Verification code has expired', field: 'code' } },
        { status: 400 }
      )
    }

    latestCode.used = true

    // Generate mock tokens
    const accessToken = `mock_access_token_${user.id}_${Date.now()}`
    const mockRefreshToken = `mock_refresh_token_${user.id}_${Date.now()}`

    // Set httpOnly refresh_token cookie (mocked — not actually httpOnly in MSW)
    return HttpResponse.json(
      {
        access_token: accessToken,
        token_type: 'bearer',
        expires_in: 900,
      },
      {
        headers: {
          'Set-Cookie': `refresh_token=${mockRefreshToken}; Path=/; SameSite=Lax; Max-Age=604800`,
        },
      }
    )
  }),

  // ---- Auth: Refresh (cookie-based) ----
  http.post('/api/v1/auth/refresh', async ({ request }) => {
    await delay(200)

    // Read refresh_token from cookie instead of request body
    const cookieHeader = request.headers.get('Cookie') || ''
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=')
        return [key, val.join('=')]
      })
    )
    const refreshToken = cookies['refresh_token']

    if (!refreshToken?.startsWith('mock_refresh_token_')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Invalid or missing refresh token', field: null } },
        { status: 401 }
      )
    }

    const accessToken = `mock_access_token_refreshed_${Date.now()}`
    return HttpResponse.json({ access_token: accessToken, expires_in: 900 })
  }),

  // ---- Auth: Logout ----
  http.post('/api/v1/auth/logout', async () => {
    await delay(100)
    // Clear the refresh_token cookie
    return new HttpResponse(null, {
      status: 204,
      headers: {
        'Set-Cookie': 'refresh_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax',
      },
    })
  }),

  // ---- Auth: Me ----
  http.get('/api/v1/auth/me', async ({ request }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    // Extract user ID from mock token
    const token = authHeader.replace('Bearer ', '')
    const match = token.match(/mock_access_token_(\d+)_/)
    if (!match) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Invalid token', field: null } },
        { status: 401 }
      )
    }

    const userId = parseInt(match[1])
    const userEntry = Object.entries(users).find(([_, u]) => u.id === userId)
    if (!userEntry) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'User not found', field: null } },
        { status: 401 }
      )
    }

    const [userEmail, userData] = userEntry

    let activeCompany = null
    if (userData.active_company_id) {
      const company = companies.find((h) => h.id === userData.active_company_id)
      if (company) {
        activeCompany = {
          id: company.id,
          name: company.name,
          inn: company.inn,
          legal_form: company.legal_form,
        }
      }
    }

    return HttpResponse.json({
      id: userData.id,
      email: userData.email,
      is_verified: userData.is_verified,
      active_company: activeCompany,
    })
  }),

  // ---- Companies: List ----
  http.get('/api/v1/companies', async ({ request }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    return HttpResponse.json(companies)
  }),

  // ---- Companies: Create ----
  http.post('/api/v1/companies', async ({ request }) => {
    await delay(300)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const body = (await request.json()) as { name: string; inn?: string; legal_form: string }
    const name = body.name?.trim()

    if (!name) {
      return HttpResponse.json(
        { detail: { code: 'VALIDATION_ERROR', message: 'Name is required', field: 'name' } },
        { status: 422 }
      )
    }

    if (companies.some((h) => h.name.toLowerCase() === name.toLowerCase())) {
      return HttpResponse.json(
        { detail: { code: 'CONFLICT', message: 'A company with this name already exists', field: 'name' } },
        { status: 409 }
      )
    }

    const newCompany = {
      id: nextCompanyId++,
      name,
      inn: body.inn || null,
      legal_form: body.legal_form,
      active_sources: ['pravo_gov_ru', 'docs_cntd_ru'],
      created_at: new Date().toISOString(),
    }
    companies.push(newCompany)

    return HttpResponse.json(
      {
        id: newCompany.id,
        name: newCompany.name,
        inn: newCompany.inn,
        legal_form: newCompany.legal_form,
      },
      { status: 201 }
    )
  }),

  // ---- Companies: Update ----
  http.put('/api/v1/companies/:id', async ({ request, params }) => {
    await delay(300)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const company = companies.find((h) => h.id === id)
    if (!company) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Company not found', field: 'company_id' } },
        { status: 404 }
      )
    }

    const body = (await request.json()) as { name?: string; inn?: string; legal_form?: string }

    if (body.name !== undefined) {
      const name = body.name.trim()
      if (companies.some((h) => h.name.toLowerCase() === name.toLowerCase() && h.id !== id)) {
        return HttpResponse.json(
          { detail: { code: 'CONFLICT', message: 'A company with this name already exists', field: 'name' } },
          { status: 409 }
        )
      }
      company.name = name
    }
    if (body.inn !== undefined) company.inn = body.inn || null
    if (body.legal_form !== undefined) company.legal_form = body.legal_form

    return HttpResponse.json({
      id: company.id,
      name: company.name,
      inn: company.inn,
      legal_form: company.legal_form,
    })
  }),

  // ---- Companies: Get Profile ----
  http.get('/api/v1/companies/:id/profile', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const company = companies.find((h) => h.id === id)
    if (!company) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Company not found', field: 'company_id' } },
        { status: 404 }
      )
    }

    const availableSources = buildAvailableSources(id, company.active_sources)

    return HttpResponse.json({
      id: company.id,
      name: company.name,
      inn: company.inn,
      legal_form: company.legal_form,
      active_sources: company.active_sources,
      available_sources: availableSources,
    })
  }),

  // ---- Companies: Update Profile ----
  http.put('/api/v1/companies/:id/profile', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const company = companies.find((h) => h.id === id)
    if (!company) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Company not found', field: 'company_id' } },
        { status: 404 }
      )
    }

    const body = (await request.json()) as {
      name?: string
      inn?: string | null
      legal_form?: string
      active_sources?: string[]
    }

    if (body.name !== undefined) {
      const name = body.name.trim()
      if (companies.some((h) => h.name.toLowerCase() === name.toLowerCase() && h.id !== id)) {
        return HttpResponse.json(
          { detail: { code: 'CONFLICT', message: 'A company with this name already exists', field: 'name' } },
          { status: 409 }
        )
      }
      company.name = name
    }
    if (body.inn !== undefined) company.inn = body.inn || null
    if (body.legal_form !== undefined) company.legal_form = body.legal_form
    if (body.active_sources !== undefined) {
      company.active_sources = body.active_sources
    }

    const availableSources = buildAvailableSources(id, company.active_sources)

    return HttpResponse.json({
      id: company.id,
      name: company.name,
      inn: company.inn,
      legal_form: company.legal_form,
      active_sources: company.active_sources,
      available_sources: availableSources,
    })
  }),

  // ---- Companies: Delete ----
  http.delete('/api/v1/companies/:id', async ({ request, params }) => {
    await delay(300)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const index = companies.findIndex((h) => h.id === id)
    if (index === -1) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Company not found', field: 'company_id' } },
        { status: 404 }
      )
    }

    // Check for user associations
    if (userCompanies.some((uh) => uh.company_id === id)) {
      return HttpResponse.json(
        { detail: { code: 'CONFLICT', message: 'Cannot delete company with existing user associations' } },
        { status: 409 }
      )
    }

    companies.splice(index, 1)
    return new HttpResponse(null, { status: 204 })
  }),

  // ---- User: Set Active Company ----
  http.put('/api/v1/user/company', async ({ request }) => {
    await delay(300)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const token = authHeader.replace('Bearer ', '')
    const match = token.match(/mock_access_token_(\d+)_/)
    if (!match) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Invalid token', field: null } },
        { status: 401 }
      )
    }

    const userId = parseInt(match[1])
    const body = (await request.json()) as { company_id: number }

    const company = companies.find((h) => h.id === body.company_id)
    if (!company) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Company not found', field: 'company_id' } },
        { status: 404 }
      )
    }

    // Auto-assign user to company if not already a member
    if (!userCompanies.some((uh) => uh.user_id === userId && uh.company_id === body.company_id)) {
      userCompanies.push({ user_id: userId, company_id: body.company_id, role: 'member' })
    }

    // Update user's active company
    const userEntry = Object.entries(users).find(([_, u]) => u.id === userId)
    if (userEntry) {
      userEntry[1].active_company_id = body.company_id
    }

    return HttpResponse.json({
      message: 'Active company set successfully',
      active_company: {
        id: company.id,
        name: company.name,
      },
    })
  }),

  // ---- Documents: Upload ----
  http.post('/api/v1/documents/upload', async ({ request }) => {
    await delay(500)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const formData = await request.formData()
    const file = formData.get('file') as File | null
    const title = formData.get('title') as string | null
    const description = formData.get('description') as string | null

    if (!file) {
      return HttpResponse.json(
        { detail: { code: 'VALIDATION_ERROR', message: 'File is required', field: 'file' } },
        { status: 422 }
      )
    }

    const fileName = file.name
    const fileType = fileName.endsWith('.pdf') ? 'pdf' : 'docx'
    const fileSize = file.size

    const docId = nextDocumentId++
    const now = new Date().toISOString()

    const newDoc: DocumentMock = {
      id: docId,
      title: title || fileName.replace(/\.[^/.]+$/, ''),
      description: description || null,
      status: 'draft',
      company_id: 1,
      created_by: { id: 1, email: 'user@example.com' },
      current_version: {
        id: docId,
        version_number: 1,
        file_type: fileType,
        file_size: fileSize,
        created_at: now,
      },
      stats: {
        sections_count: 3,
        tables_count: 1,
        terms_count: 2,
        abbreviations_count: 1,
        versions_count: 1,
      },
      created_at: now,
      updated_at: now,
    }
    documents.push(newDoc)

    return HttpResponse.json(
      {
        id: docId,
        title: newDoc.title,
        status: 'draft',
        file_type: fileType,
        file_size: fileSize,
        sections_count: 3,
        tables_count: 1,
        terms_count: 2,
        abbreviations_count: 1,
        created_at: now,
      },
      { status: 201 }
    )
  }),

  // ---- Documents: List ----
  http.get('/api/v1/documents', async ({ request }) => {
    await delay(300)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    const search = url.searchParams.get('search')?.toLowerCase()
    const page = parseInt(url.searchParams.get('page') || '1')
    const pageSize = parseInt(url.searchParams.get('page_size') || '10')

    let filtered = [...documents]

    if (status && status !== 'all') {
      filtered = filtered.filter((d) => d.status === status)
    }

    if (search) {
      filtered = filtered.filter((d) => d.title.toLowerCase().includes(search))
    }

    const total = filtered.length
    const pages = Math.ceil(total / pageSize)
    const start = (page - 1) * pageSize
    const items = filtered.slice(start, start + pageSize).map((d) => ({
      id: d.id,
      title: d.title,
      status: d.status,
      file_type: d.current_version?.file_type || 'docx',
      file_size: d.current_version?.file_size || 0,
      version_number: d.current_version?.version_number || 1,
      has_terms: (d.stats?.terms_count || 0) > 0,
      has_abbreviations: (d.stats?.abbreviations_count || 0) > 0,
      created_by: d.created_by,
      created_at: d.created_at,
      updated_at: d.updated_at,
    }))

    return HttpResponse.json({ items, total, page, page_size: pageSize, pages })
  }),

  // ---- Documents: Get Detail ----
  http.get('/api/v1/documents/:id', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const doc = documents.find((d) => d.id === id)
    if (!doc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    return HttpResponse.json(doc)
  }),

  // ---- Documents: Update ----
  http.put('/api/v1/documents/:id', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const doc = documents.find((d) => d.id === id)
    if (!doc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    const body = (await request.json()) as { title?: string; description?: string; status?: string }
    if (body.title !== undefined) doc.title = body.title
    if (body.description !== undefined) doc.description = body.description
    if (body.status !== undefined) doc.status = body.status as DocumentMockStatus
    doc.updated_at = new Date().toISOString()

    return HttpResponse.json(doc)
  }),

  // ---- Documents: Archive (Delete) ----
  http.delete('/api/v1/documents/:id', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const index = documents.findIndex((d) => d.id === id)
    if (index === -1) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    documents.splice(index, 1)
    return new HttpResponse(null, { status: 204 })
  }),

  // ---- Documents: Versions ----
  http.get('/api/v1/documents/:id/versions', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const doc = documents.find((d) => d.id === id)
    if (!doc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    const versionsForDoc = documentVersionsList
      .filter((v) => v.document_id === id)
      .map((v) => ({
        id: v.id,
        version_number: v.version_number,
        file_type: v.file_type,
        file_size: v.file_size,
        uploaded_by: v.uploaded_by,
        sections_count: v.sections_count,
        tables_count: v.tables_count,
        version_notes: v.version_notes,
        created_at: v.created_at,
      }))

    return HttpResponse.json({ items: versionsForDoc })
  }),

  // ---- Documents: Create Version ----
  http.post('/api/v1/documents/:id/versions', async ({ request, params }) => {
    await delay(500)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const doc = documents.find((d) => d.id === id)
    if (!doc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    const formData = await request.formData()
    const file = formData.get('file') as File | null
    const versionNotes = formData.get('version_notes') as string | null

    if (!file) {
      return HttpResponse.json(
        { detail: { code: 'VALIDATION_ERROR', message: 'File is required', field: 'file' } },
        { status: 422 }
      )
    }

    const fileName = file.name
    const fileType = fileName.endsWith('.pdf') ? 'pdf' : 'docx'
    const newVersionNumber = (doc.current_version?.version_number || 0) + 1
    const now = new Date().toISOString()
    const newVersionId = versionsNextId++

    const newVersion = {
      id: newVersionId,
      document_id: id,
      version_number: newVersionNumber,
      file_type: fileType,
      file_size: file.size,
      uploaded_by: { id: 1, email: 'user@example.com' },
      sections_count: doc.stats.sections_count,
      tables_count: doc.stats.tables_count,
      version_notes: versionNotes,
      created_at: now,
    }

    documentVersionsList.push(newVersion)

    // Update document current version
    doc.current_version = {
      id: newVersionId,
      version_number: newVersionNumber,
      file_type: fileType,
      file_size: file.size,
      created_at: now,
    }
    doc.stats.versions_count = (doc.stats.versions_count || 0) + 1
    doc.updated_at = now

    return HttpResponse.json(
      {
        id: newVersionId,
        version_number: newVersionNumber,
        file_type: fileType,
        file_size: file.size,
        uploaded_by: { id: 1, email: 'user@example.com' },
        sections_count: doc.stats.sections_count,
        tables_count: doc.stats.tables_count,
        version_notes: versionNotes,
        created_at: now,
      },
      { status: 201 }
    )
  }),

  // ---- Documents: Diff ----
  http.get('/api/v1/documents/:id/diff', async ({ request, params }) => {
    await delay(300)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const url = new URL(request.url)
    const from = parseInt(url.searchParams.get('from') || '1')
    const to = parseInt(url.searchParams.get('to') || '1')

    const doc = documents.find((d) => d.id === id)
    if (!doc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    const fromVersion = documentVersionsList.find((v) => v.document_id === id && v.version_number === from)
    const toVersion = documentVersionsList.find((v) => v.document_id === id && v.version_number === to)

    return HttpResponse.json({
      from_version: from,
      to_version: to,
      changes: [
        { field: 'sections_count', old_value: String(fromVersion?.sections_count || 0), new_value: String(toVersion?.sections_count || 0) },
        { field: 'tables_count', old_value: String(fromVersion?.tables_count || 0), new_value: String(toVersion?.tables_count || 0) },
        { field: 'file_size', old_value: String(fromVersion?.file_size || 0), new_value: String(toVersion?.file_size || 0) },
      ],
    })
  }),

  // ---- Documents: Download Version ----
  http.get('/api/v1/documents/versions/:versionId/download', async () => {
    await delay(300)
    const content = 'Mock document content for testing purposes.'
    return new HttpResponse(content, {
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': 'attachment; filename="document.docx"',
      },
    })
  }),

  // ---- Documents: Sections ----
  http.get('/api/v1/documents/:id/sections', async ({ request }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    return HttpResponse.json({
      sections: [
        {
          id: 1,
          title: 'Общие положения',
          level: 1,
          order_num: 1,
          content: 'Настоящий документ определяет порядок работы с регламентами в холдинге. Документ обязателен для всех сотрудников.',
          children: [
            {
              id: 2,
              title: 'Область применения',
              level: 2,
              order_num: 1,
              content: 'Документ распространяется на все подразделения холдинга, участвующие в процессе создания и согласования регламентов.',
              children: [],
            },
            {
              id: 3,
              title: 'Нормативные ссылки',
              level: 2,
              order_num: 2,
              content: 'Настоящий документ разработан в соответствии с:\n- Федеральным законом № 123-ФЗ\n- Внутренними регламентами холдинга',
              children: [],
            },
          ],
        },
        {
          id: 4,
          title: 'Термины и определения',
          level: 1,
          order_num: 2,
          content: 'В настоящем документе используются следующие термины и определения.',
          children: [
            {
              id: 5,
              title: 'Регламент',
              level: 2,
              order_num: 1,
              content: 'Документ, содержащий обязательные правила и процедуры выполнения бизнес-процессов.',
              children: [],
            },
            {
              id: 6,
              title: 'Холдинг',
              level: 2,
              order_num: 2,
              content: 'Группа взаимосвязанных организаций, объединённых общим управлением.',
              children: [],
            },
          ],
        },
        {
          id: 7,
          title: 'Порядок разработки регламентов',
          level: 1,
          order_num: 3,
          content: 'Разработка регламентов осуществляется в соответствии с ежегодным планом нормотворческой деятельности.',
          children: [
            {
              id: 8,
              title: 'Инициация разработки',
              level: 2,
              order_num: 1,
              content: 'Основанием для разработки регламента является служебная записка руководителя подразделения.',
              children: [
                {
                  id: 9,
                  title: 'Подготовка проекта',
                  level: 3,
                  order_num: 1,
                  content: 'Проект регламента подготавливается ответственным исполнителем в срок не более 30 рабочих дней.',
                  children: [],
                },
              ],
            },
          ],
        },
        {
          id: 10,
          title: 'Заключительные положения',
          level: 1,
          order_num: 4,
          content: 'Настоящий документ вступает в силу с даты его утверждения.',
          children: [],
        },
      ],
    })
  }),

  // ---- Documents: Terms ----
  http.get('/api/v1/documents/:id/terms', async ({ request }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    return HttpResponse.json({
      terms: [
        { id: 1, term: 'Регламент', definition: 'Документ, содержащий обязательные правила и процедуры выполнения бизнес-процессов.' },
        { id: 2, term: 'Холдинг', definition: 'Группа взаимосвязанных организаций, объединённых общим управлением.' },
        { id: 3, term: 'Нормотворческая деятельность', definition: 'Деятельность по разработке, утверждению и актуализации внутренних нормативных документов.' },
        { id: 4, term: 'Ответственный исполнитель', definition: 'Сотрудник, назначенный руководителем подразделения для разработки проекта регламента.' },
        { id: 5, term: 'Согласование', definition: 'Процедура проверки проекта регламента заинтересованными сторонами.' },
      ],
    })
  }),

  // ---- Documents: Abbreviations ----
  http.get('/api/v1/documents/:id/abbreviations', async ({ request }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    return HttpResponse.json({
      abbreviations: [
        { id: 1, abbreviation: 'НПА', full_form: 'Нормативный правовой акт' },
        { id: 2, abbreviation: 'ООО', full_form: 'Общество с ограниченной ответственностью' },
        { id: 3, abbreviation: 'СЭД', full_form: 'Система электронного документооборота' },
      ],
    })
  }),

  // ---- Generator ----
  http.post('/api/v1/generator/generate', async ({ request }) => {
    await delay(3000)  // Simulate 3s generation

    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const body = await request.formData()
    const context = body.get('context') as string

    return HttpResponse.json({
      id: Date.now(),
      title: 'Сгенерированный регламент',
      status: 'draft',
      file_type: 'docx',
      file_size: 24576,
      current_version: {
        id: 1,
        version_number: 1,
        file_type: 'docx',
        file_size: 24576,
        created_at: new Date().toISOString(),
      },
      generated_with_mock: true,
      created_at: new Date().toISOString(),
    }, { status: 201 })
  }),

  // ---- Documents: Links ----
  http.get('/api/v1/documents/:id/links', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const doc = documents.find((d) => d.id === id)
    if (!doc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    // Links where this document is source or target
    const links = documentLinks
      .filter((l) => l.source_document_id === id || l.target_document_id === id)
      .map((l) => {
        const sourceDoc = documents.find((d) => d.id === l.source_document_id)
        const targetDoc = documents.find((d) => d.id === l.target_document_id)
        return {
          ...l,
          source_document: sourceDoc
            ? {
                id: sourceDoc.id,
                title: sourceDoc.title,
                status: sourceDoc.status,
                file_type: sourceDoc.current_version?.file_type || 'docx',
                file_size: sourceDoc.current_version?.file_size || 0,
                version_number: sourceDoc.current_version?.version_number || 1,
                has_terms: (sourceDoc.stats?.terms_count || 0) > 0,
                has_abbreviations: (sourceDoc.stats?.abbreviations_count || 0) > 0,
                created_by: sourceDoc.created_by,
                created_at: sourceDoc.created_at,
                updated_at: sourceDoc.updated_at,
              }
            : undefined,
          target_document: targetDoc
            ? {
                id: targetDoc.id,
                title: targetDoc.title,
                status: targetDoc.status,
                file_type: targetDoc.current_version?.file_type || 'docx',
                file_size: targetDoc.current_version?.file_size || 0,
                version_number: targetDoc.current_version?.version_number || 1,
                has_terms: (targetDoc.stats?.terms_count || 0) > 0,
                has_abbreviations: (targetDoc.stats?.abbreviations_count || 0) > 0,
                created_by: targetDoc.created_by,
                created_at: targetDoc.created_at,
                updated_at: targetDoc.updated_at,
              }
            : undefined,
        }
      })

    return HttpResponse.json({ items: links })
  }),

  http.post('/api/v1/documents/:id/links', async ({ request, params }) => {
    await delay(300)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const id = parseInt(params.id as string)
    const doc = documents.find((d) => d.id === id)
    if (!doc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Document not found', field: 'id' } },
        { status: 404 }
      )
    }

    const body = (await request.json()) as { target_document_id: number; link_type: string; description?: string }
    const targetDoc = documents.find((d) => d.id === body.target_document_id)
    if (!targetDoc) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Target document not found', field: 'target_document_id' } },
        { status: 404 }
      )
    }

    const now = new Date().toISOString()
    const newLink = {
      id: nextLinkId++,
      source_document_id: id,
      target_document_id: body.target_document_id,
      link_type: body.link_type as 'references' | 'amends' | 'supersedes' | 'related',
      is_manual: true,
      description: body.description || null,
      created_by: { id: 1, email: 'user@example.com' },
      created_at: now,
    }
    documentLinks.push(newLink)

    const sourceDoc = documents.find((d) => d.id === newLink.source_document_id)
    return HttpResponse.json(
      {
        ...newLink,
        source_document: sourceDoc
          ? {
              id: sourceDoc.id,
              title: sourceDoc.title,
              status: sourceDoc.status,
              file_type: sourceDoc.current_version?.file_type || 'docx',
              file_size: sourceDoc.current_version?.file_size || 0,
              version_number: sourceDoc.current_version?.version_number || 1,
              has_terms: (sourceDoc.stats?.terms_count || 0) > 0,
              has_abbreviations: (sourceDoc.stats?.abbreviations_count || 0) > 0,
              created_by: sourceDoc.created_by,
              created_at: sourceDoc.created_at,
              updated_at: sourceDoc.updated_at,
            }
          : undefined,
        target_document: targetDoc
          ? {
              id: targetDoc.id,
              title: targetDoc.title,
              status: targetDoc.status,
              file_type: targetDoc.current_version?.file_type || 'docx',
              file_size: targetDoc.current_version?.file_size || 0,
              version_number: targetDoc.current_version?.version_number || 1,
              has_terms: (targetDoc.stats?.terms_count || 0) > 0,
              has_abbreviations: (targetDoc.stats?.abbreviations_count || 0) > 0,
              created_by: targetDoc.created_by,
              created_at: targetDoc.created_at,
              updated_at: targetDoc.updated_at,
            }
          : undefined,
      },
      { status: 201 }
    )
  }),

  http.delete('/api/v1/documents/links/:linkId', async ({ request, params }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    const linkId = parseInt(params.linkId as string)
    const index = documentLinks.findIndex((l) => l.id === linkId)
    if (index === -1) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Link not found', field: 'linkId' } },
        { status: 404 }
      )
    }

    documentLinks.splice(index, 1)
    return new HttpResponse(null, { status: 204 })
  }),

  // ---- Legislation: Available Sources ----
  http.get('/api/v1/legislation/sources/available', async ({ request }) => {
    await delay(200)

    // Get the auth header to determine company
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(BUILT_IN_SOURCES.map((s) => ({ ...s, is_active: false })))
    }

    // Try to find the user's active company
    const token = authHeader.replace('Bearer ', '')
    const match = token.match(/mock_access_token_(\d+)_/)
    let activeCompanyId: number | null = null

    if (match) {
      const userId = parseInt(match[1])
      const userEntry = Object.entries(users).find(([_, u]) => u.id === userId)
      if (userEntry) {
        activeCompanyId = userEntry[1].active_company_id
      }
    }

    const company = companies.find((h) => h.id === activeCompanyId)
    const activeSources = company ? company.active_sources : []
    const companyId = company ? company.id : 1

    const availableSources = buildAvailableSources(companyId, activeSources)
    return HttpResponse.json(availableSources)
  }),

  // ---- Legislation: Search ----
  http.get('/api/v1/legislation/search', async ({ request }) => {
    await delay(400)
    const url = new URL(request.url)
    const query = url.searchParams.get('query') || ''
    const source = url.searchParams.get('source') || ''
    const page = parseInt(url.searchParams.get('page') || '1')
    const pageSize = 10

    if (!query || query.length < 3) {
      return HttpResponse.json({
        query,
        source: source || 'all',
        items: [],
        total: 0,
        page,
      })
    }

    // Mock results per source
    const mockResults: Record<string, Array<{
      title: string
      number: string | null
      date: string | null
      source: string
      url: string
      snippet: string
    }>> = {
      'all': [
        { title: 'О персональных данных', number: '152-ФЗ', date: '2006-07-27', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102108391', snippet: 'Настоящий Федеральный закон регулирует отношения, связанные с обработкой персональных данных...' },
        { title: 'Об информации, информационных технологиях и о защите информации', number: '149-ФЗ', date: '2006-07-27', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102108264', snippet: 'Настоящий Федеральный закон регулирует отношения, возникающие при осуществлении права на поиск...' },
        { title: 'Об акционерных обществах', number: '208-ФЗ', date: '1995-12-26', source: 'docs.cntd.ru', url: 'https://docs.cntd.ru/document/9003169', snippet: 'Настоящий Федеральный закон определяет порядок создания, реорганизации, ликвидации акционерных обществ...' },
        { title: 'О защите конкуренции', number: '135-ФЗ', date: '2006-07-26', source: 'docs.cntd.ru', url: 'https://docs.cntd.ru/document/902050092', snippet: 'Настоящий Федеральный закон определяет организационные и правовые основы защиты конкуренции...' },
        { title: 'Трудовой кодекс Российской Федерации', number: '197-ФЗ', date: '2001-12-30', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102079982', snippet: 'Трудовой кодекс Российской Федерации регулирует трудовые отношения...' },
        { title: 'Об обществах с ограниченной ответственностью', number: '14-ФЗ', date: '1998-02-08', source: 'docs.cntd.ru', url: 'https://docs.cntd.ru/document/9003498', snippet: 'Настоящий Федеральный закон определяет правовое положение ООО...' },
        { title: 'О противодействии коррупции', number: '273-ФЗ', date: '2008-12-25', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102123790', snippet: 'Настоящий Федеральный закон устанавливает основные принципы противодействия коррупции...' },
      ],
      'pravo_gov_ru': [
        { title: 'О персональных данных', number: '152-ФЗ', date: '2006-07-27', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102108391', snippet: 'Настоящий Федеральный закон регулирует отношения, связанные с обработкой персональных данных...' },
        { title: 'Об информации, информационных технологиях и о защите информации', number: '149-ФЗ', date: '2006-07-27', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102108264', snippet: 'Настоящий Федеральный закон регулирует отношения, возникающие при осуществлении права на поиск...' },
        { title: 'Трудовой кодекс Российской Федерации', number: '197-ФЗ', date: '2001-12-30', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102079982', snippet: 'Трудовой кодекс Российской Федерации регулирует трудовые отношения...' },
        { title: 'О противодействии коррупции', number: '273-ФЗ', date: '2008-12-25', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102123790', snippet: 'Настоящий Федеральный закон устанавливает основные принципы противодействия коррупции...' },
        { title: 'О защите конкуренции', number: '135-ФЗ', date: '2006-07-26', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102108317', snippet: 'Настоящий Федеральный закон определяет организационные и правовые основы защиты конкуренции...' },
        { title: 'Об обществах с ограниченной ответственностью', number: '14-ФЗ', date: '1998-02-08', source: 'pravo.gov.ru', url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102049710', snippet: 'Настоящий Федеральный закон определяет правовое положение ООО...' },
      ],
      'docs_cntd_ru': [
        { title: 'ГОСТ Р 7.0.97-2016', number: null, date: '2016-12-01', source: 'docs.cntd.ru', url: 'https://docs.cntd.ru/document/1200142677', snippet: 'Система стандартов по информации, библиотечному и издательскому делу. Организационно-распорядительная документация...' },
        { title: 'Об акционерных обществах', number: '208-ФЗ', date: '1995-12-26', source: 'docs.cntd.ru', url: 'https://docs.cntd.ru/document/9003169', snippet: 'Настоящий Федеральный закон определяет порядок создания, реорганизации, ликвидации акционерных обществ...' },
        { title: 'О защите конкуренции', number: '135-ФЗ', date: '2006-07-26', source: 'docs.cntd.ru', url: 'https://docs.cntd.ru/document/902050092', snippet: 'Настоящий Федеральный закон определяет организационные и правовые основы защиты конкуренции...' },
        { title: 'Об обществах с ограниченной ответственностью', number: '14-ФЗ', date: '1998-02-08', source: 'docs.cntd.ru', url: 'https://docs.cntd.ru/document/9003498', snippet: 'Настоящий Федеральный закон определяет правовое положение общества с ограниченной ответственностью...' },
      ],
    }

    // Fall back to 'all' if the requested source is not in mockResults
    const itemsForSource = mockResults[source] || mockResults['all'] || []

    // Filter by query
    const q = query.toLowerCase()
    const filtered = itemsForSource.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        (item.number && item.number.toLowerCase().includes(q)) ||
        item.snippet.toLowerCase().includes(q)
    )

    const total = filtered.length
    const start = (page - 1) * pageSize
    const items = filtered.slice(start, start + pageSize)

    return HttpResponse.json({
      query,
      source: source || 'all',
      items,
      total,
      page,
    })
  }),

  // ---- Legislation: Sources ----
  http.get('/api/v1/legislation/sources', async () => {
    await delay(200)
    return HttpResponse.json(legislationSources)
  }),

  http.post('/api/v1/legislation/sources', async ({ request }) => {
    await delay(300)
    const body = (await request.json()) as {
      name: string
      source_type: string
      url_template?: string
      parser_type?: string
      selector?: string
      is_paid?: boolean
      icon_url?: string
      description?: string
    }

    if (!body.name || !body.source_type) {
      return HttpResponse.json(
        { detail: { code: 'VALIDATION_ERROR', message: 'Name and source_type are required', field: 'name' } },
        { status: 422 }
      )
    }

    const now = new Date().toISOString()
    const newSource = {
      id: nextLegislationSourceId++,
      company_id: 1,
      name: body.name,
      source_type: body.source_type as 'template_url' | 'static_list' | 'custom_parser',
      url_template: body.url_template || null,
      parser_type: body.parser_type || null,
      selector: body.selector || null,
      is_active: true,
      is_paid: body.is_paid || false,
      icon_url: body.icon_url || null,
      description: body.description || null,
      created_at: now,
      updated_at: now,
    }
    legislationSources.push(newSource)
    return HttpResponse.json(newSource, { status: 201 })
  }),

  http.get('/api/v1/legislation/sources/:id', async ({ params }) => {
    await delay(200)
    const id = parseInt(params.id as string)
    const source = legislationSources.find((s) => s.id === id)
    if (!source) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Source not found', field: 'id' } },
        { status: 404 }
      )
    }
    return HttpResponse.json(source)
  }),

  http.put('/api/v1/legislation/sources/:id', async ({ request, params }) => {
    await delay(300)
    const id = parseInt(params.id as string)
    const source = legislationSources.find((s) => s.id === id)
    if (!source) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Source not found', field: 'id' } },
        { status: 404 }
      )
    }

    const body = (await request.json()) as {
      name?: string
      source_type?: string
      url_template?: string
      parser_type?: string
      selector?: string
      is_paid?: boolean
      is_active?: boolean
      icon_url?: string
      description?: string
    }

    if (body.name !== undefined) source.name = body.name
    if (body.source_type !== undefined) source.source_type = body.source_type as 'template_url' | 'static_list' | 'custom_parser'
    if (body.url_template !== undefined) source.url_template = body.url_template || null
    if (body.parser_type !== undefined) source.parser_type = body.parser_type || null
    if (body.selector !== undefined) source.selector = body.selector || null
    if (body.is_paid !== undefined) source.is_paid = body.is_paid
    if (body.is_active !== undefined) source.is_active = body.is_active
    if (body.icon_url !== undefined) source.icon_url = body.icon_url || null
    if (body.description !== undefined) source.description = body.description || null
    source.updated_at = new Date().toISOString()

    return HttpResponse.json(source)
  }),

  http.delete('/api/v1/legislation/sources/:id', async ({ params }) => {
    await delay(200)
    const id = parseInt(params.id as string)
    const index = legislationSources.findIndex((s) => s.id === id)
    if (index === -1) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Source not found', field: 'id' } },
        { status: 404 }
      )
    }
    legislationSources.splice(index, 1)
    return new HttpResponse(null, { status: 204 })
  }),

  http.post('/api/v1/legislation/sources/:id/search', async ({ request, params }) => {
    await delay(500)
    const id = parseInt(params.id as string)
    const source = legislationSources.find((s) => s.id === id)
    if (!source) {
      return HttpResponse.json(
        { detail: { code: 'NOT_FOUND', message: 'Source not found', field: 'id' } },
        { status: 404 }
      )
    }

    // If source is paid, return a subscription-required message
    if (source.is_paid) {
      return HttpResponse.json({
        items: [],
        message: 'Для поиска по платному источнику требуется подписка',
      })
    }

    const body = (await request.json()) as { query: string }
    const query = body.query?.toLowerCase() || ''

    if (!query || query.length < 2) {
      return HttpResponse.json([])
    }

    // Mock search results
    const mockResults = [
      {
        title: 'Федеральный закон "О персональных данных"',
        url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102108391',
        snippet: 'Настоящий Федеральный закон регулирует отношения, связанные с обработкой персональных данных...',
        date: '2006-07-27',
      },
      {
        title: 'Федеральный закон "Об информации, информационных технологиях и о защите информации"',
        url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102108264',
        snippet: 'Настоящий Федеральный закон регулирует отношения, возникающие при осуществлении права на поиск...',
        date: '2006-07-27',
      },
      {
        title: 'Постановление Правительства РФ № 123',
        url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102123456',
        snippet: 'О порядке обработки персональных данных в государственных информационных системах...',
        date: '2020-02-15',
      },
      {
        title: 'Приказ Минцифры России № 456',
        url: 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102654321',
        snippet: 'Об утверждении требований к защите информации в автоматизированных системах управления...',
        date: '2023-05-10',
      },
    ]

    const filteredResults = query
      ? mockResults.filter(
          (r) =>
            r.title.toLowerCase().includes(query) ||
            r.snippet.toLowerCase().includes(query)
        )
      : mockResults

    return HttpResponse.json(filteredResults)
  }),

  // ---- Documents: Impact Map ----
  http.get('/api/v1/documents/:id/impact', async ({ params }) => {
    await delay(300)
    const id = parseInt(params.id as string)

    // Return mock impact map data based on document id
    const impactMaps: Record<number, any> = {
      1: {
        document_id: 1,
        document_title: 'Регламент разработки внутренних нормативных документов',
        incoming: {
          documents: [
            { id: 4, title: 'Регламент проведения внутреннего аудита', type: 'references', date: '2026-05-01' },
            { id: 2, title: 'Инструкция по работе с СЭД', type: 'related', date: '2026-06-18' },
          ],
        },
        outgoing: {
          documents: [
            { id: 4, title: 'Регламент проведения внутреннего аудита', type: 'amends', date: '2026-06-15' },
          ],
        },
      },
      2: {
        document_id: 2,
        document_title: 'Инструкция по работе с системой электронного документооборота',
        incoming: {
          documents: [
            { id: 1, title: 'Регламент разработки ВНД', type: 'references', date: '2026-06-15' },
          ],
        },
        outgoing: {
          documents: [],
        },
      },
      3: {
        document_id: 3,
        document_title: 'Политика конфиденциальности и обработки персональных данных',
        incoming: {
          documents: [],
        },
        outgoing: {
          documents: [],
        },
      },
      4: {
        document_id: 4,
        document_title: 'Регламент проведения внутреннего аудита',
        incoming: {
          documents: [
            { id: 1, title: 'Регламент разработки ВНД', type: 'supersedes', date: '2026-06-15' },
          ],
        },
        outgoing: {
          documents: [
            { id: 1, title: 'Регламент разработки ВНД', type: 'references', date: '2026-05-01' },
          ],
        },
      },
    }

    const map = impactMaps[id]
    if (!map) {
      return HttpResponse.json({
        document_id: id,
        document_title: 'Документ #' + id,
        incoming: { documents: [] },
        outgoing: { documents: [] },
      })
    }

    return HttpResponse.json(map)
  }),

  // ---- Documents: Impact Graph ----
  http.get('/api/v1/documents/:id/impact/graph', async ({ params }) => {
    await delay(300)
    const id = parseInt(params.id as string)

    const impactMaps: Record<number, any> = {
      1: {
        document_title: 'Регламент разработки внутренних нормативных документов',
        incoming: {
          documents: [
            { id: 4, title: 'Регламент проведения внутреннего аудита', type: 'references' },
            { id: 2, title: 'Инструкция по работе с СЭД', type: 'related' },
          ],
        },
        outgoing: {
          documents: [
            { id: 4, title: 'Регламент проведения внутреннего аудита', type: 'amends' },
          ],
        },
      },
      2: {
        document_title: 'Инструкция по работе с системой электронного документооборота',
        incoming: {
          documents: [
            { id: 1, title: 'Регламент разработки ВНД', type: 'references' },
          ],
        },
        outgoing: { documents: [] },
      },
      3: {
        document_title: 'Политика конфиденциальности и обработки персональных данных',
        incoming: { documents: [] },
        outgoing: { documents: [] },
      },
      4: {
        document_title: 'Регламент проведения внутреннего аудита',
        incoming: {
          documents: [
            { id: 1, title: 'Регламент разработки ВНД', type: 'supersedes' },
          ],
        },
        outgoing: {
          documents: [
            { id: 1, title: 'Регламент разработки ВНД', type: 'references' },
          ],
        },
      },
    }

    const map = impactMaps[id]
    if (!map) {
      return HttpResponse.json({
        nodes: [{ id: `doc-${id}`, label: 'Документ #' + id, type: 'document', documentId: id }],
        edges: [],
      })
    }

    const graph = buildImpactGraphFromMap(id, map)
    return HttpResponse.json(graph)
  }),

  // ---- Documents: Tables ----
  http.get('/api/v1/documents/:id/tables', async ({ request }) => {
    await delay(200)
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: { code: 'UNAUTHORIZED', message: 'Not authenticated', field: null } },
        { status: 401 }
      )
    }

    return HttpResponse.json({
      tables: [
        {
          id: 1,
          caption: 'Этапы разработки регламента',
          section_title: 'Порядок разработки регламентов',
          order_num: 1,
          rows_count: 4,
          cols_count: 3,
          html_content: `<table style="width:100%; border-collapse: collapse;">
<thead>
<tr style="background: #f5f5f5;">
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Этап</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Срок</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Ответственный</th>
</tr>
</thead>
<tbody>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Инициация</td><td style="padding: 8px; border: 1px solid #ddd;">5 дней</td><td style="padding: 8px; border: 1px solid #ddd;">Руководитель подразделения</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Разработка проекта</td><td style="padding: 8px; border: 1px solid #ddd;">30 дней</td><td style="padding: 8px; border: 1px solid #ddd;">Ответственный исполнитель</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Согласование</td><td style="padding: 8px; border: 1px solid #ddd;">10 дней</td><td style="padding: 8px; border: 1px solid #ddd;">Заинтересованные стороны</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">Утверждение</td><td style="padding: 8px; border: 1px solid #ddd;">3 дня</td><td style="padding: 8px; border: 1px solid #ddd;">Генеральный директор</td></tr>
</tbody>
</table>`,
        },
        {
          id: 2,
          caption: 'Форматы документов',
          section_title: 'Общие положения',
          order_num: 1,
          rows_count: 3,
          cols_count: 2,
          html_content: `<table style="width:100%; border-collapse: collapse;">
<thead>
<tr style="background: #f5f5f5;">
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Формат</th>
<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Описание</th>
</tr>
</thead>
<tbody>
<tr><td style="padding: 8px; border: 1px solid #ddd;">DOCX</td><td style="padding: 8px; border: 1px solid #ddd;">Документ Microsoft Word с поддержкой стилей и форматирования</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">PDF</td><td style="padding: 8px; border: 1px solid #ddd;">Портативный формат документа для финальных версий</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;">ODT</td><td style="padding: 8px; border: 1px solid #ddd;">Открытый формат документов (не поддерживается)</td></tr>
</tbody>
</table>`,
        },
      ],
    })
  }),
]
